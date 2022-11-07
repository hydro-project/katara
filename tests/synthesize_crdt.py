import contextlib
import csv
from time import time
from typing import List
from katara.search_structures import search_crdt_structures
from metalift.analysis import CodeInfo
from metalift.ir import *
import katara.lattices as lat
from katara.auto_grammar import all_node_id_gets, auto_grammar, expand_lattice_logic
import sys
import multiprocessing as mp
from metalift.maps_lang import mapsLang

from metalift.synthesize_auto import synthesize

def fold_conditions(out, conditions):
    for c in conditions:
        out = Ite(c, out, out)
    return out

# we can make equivalence and state invariant shallower because
# they are augmented with query and lattice validity checks

def grammarEquivalence(inputState, synthState, queryParams, baseDepth):
    return auto_grammar(
        Bool(),
        max(baseDepth - 1, 1),
        inputState, synthState, *queryParams
    )


def grammarStateInvariant(synthState, synthStateStructure, baseDepth, invariantBoost):
    state_valid = And(*[
        synthStateStructure[i].check_is_valid(
            TupleGet(synthState, IntLit(i))
        )
        for i in range(len(synthStateStructure))
    ])

    return And(
        state_valid,
        auto_grammar(Bool(), max(baseDepth - 1, 1) + invariantBoost, synthState)
    )


def grammarSupportedCommand(synthState, args, synthStateStructure, baseDepth, invariantBoost):
    conditions = [Eq(a, IntLit(1)) for a in args if a.type == EnumInt()]

    out = auto_grammar(
        Bool(), baseDepth + invariantBoost,
        synthState, *args,
        *expand_lattice_logic(*[
            (TupleGet(synthState, IntLit(i)), synthStateStructure[i])
            for i in range(len(synthStateStructure))
        ]),
        enable_ite=True
    )

    return fold_conditions(out, conditions)

# we make query deeper because it requires more computation

def grammarQuery(name: str, args: List[Expr], retT: Type, baseDepth):
    if retT == EnumInt():
        condition = auto_grammar(
            Bool(),
            baseDepth + 1,
            *args,
            allow_node_id_reductions=True,
        )

        summary = Ite(condition, IntLit(1), IntLit(0))
    else:
        summary = auto_grammar(
            parseTypeRef(retT), baseDepth + 1,
            *args,
            enable_ite=True,
            allow_node_id_reductions=True,
        )

    return Synth(name, summary, *args)


def grammar(ci: CodeInfo, synthStateStructure, baseDepth):
    name = ci.name

    if name.startswith("inv"):
        raise Exception("no invariant")
    else:  # ps
        inputState = ci.readVars[0]
        args = ci.readVars[1:]

        conditions = [Eq(a, IntLit(1)) for a in args if a.type == EnumInt()]

        non_associative_data = []
        for a in args:
            if a.type == NodeIDInt():
                non_associative_data = all_node_id_gets(
                    inputState, a,
                    auto_grammar(None, 0, *args)
                )
                break

        out = Tuple(
            *[
                synthStateStructure[i].merge(
                    TupleGet(inputState, IntLit(i)),
                    fold_conditions(auto_grammar(
                        TupleGet(inputState, IntLit(i)).type,
                        baseDepth,
                        *args,
                        *non_associative_data
                    ), conditions)
                )
                for i in range(len(synthStateStructure))
            ],
        )

        return Synth(name, out, *ci.modifiedVars, *ci.readVars)


def initState(synthStateStructure):
    return Tuple(
        *[auto_grammar(elem.ir_type(), 1, elem.bottom()) for elem in synthStateStructure]
    )

def targetLang():
    return mapsLang()


benchmarks = {
    "flag_dw": {
        "ll_name": "sequential_flag",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)), # if first is enable
            BoolLit(True), # second can be anything
            Not(Eq(arg2[0], IntLit(1))), # but if remove, must be remove next
        ),
        "opPrecondition": lambda op: Ge(op[-1], IntLit(1)),
        "stateTypeHint": EnumInt(),
        "opArgTypeHint": [EnumInt(), ClockInt()],
        "queryArgTypeHint": None,
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.LexicalProduct(lat.MaxInt(ClockInt()), lat.OrBool()),),
    },
    "flag_ew": {
        "ll_name": "sequential_flag",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)), # if first is enable
            Eq(arg2[0], IntLit(1)), # second must be enable
            BoolLit(True), # but if remove, can be anything next
        ),
        "opPrecondition": lambda op: Ge(op[-1], IntLit(1)),
        "stateTypeHint": EnumInt(),
        "opArgTypeHint": [EnumInt(), ClockInt()],
        "queryArgTypeHint": None,
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.LexicalProduct(lat.MaxInt(ClockInt()), lat.OrBool()),),
    },
    "lww_register": {
        "ll_name": "sequential_register",
        "inOrder": lambda arg1, arg2: Ge(arg2[0], arg1[0]),
        "opPrecondition": lambda op: And(
            Ge(op[-1], IntLit(1)),
            Ge(op[0], IntLit(0))
        ),
        "stateTypeHint": OpaqueInt(),
        "opArgTypeHint": [OpaqueInt(), ClockInt()],
        "queryArgTypeHint": [],
        "queryRetTypeHint": OpaqueInt(),
        "fixedLatticeType": (lat.LexicalProduct(lat.MaxInt(ClockInt()), lat.MaxInt(OpaqueInt())),),
    },
    "g_set": {
        "ll_name": "sequential1",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)),  # if first command is insert
            Eq(arg2[0], IntLit(1)),  # second must be insert
            BoolLit(True),  # but if remove, can be anything next
        ),
        "opPrecondition": lambda op: BoolLit(True),
        "stateTypeHint": SetT(OpaqueInt()),
        "opArgTypeHint": [EnumInt(), OpaqueInt()],
        "queryArgTypeHint": [OpaqueInt()],
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.Set(OpaqueInt()),),
    },
    "2p_set": {
        "ll_name": "sequential1",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)),  # if first command is insert
            BoolLit(True),  # second can be insert or remove
            Not(Eq(arg2[0], IntLit(1))),  # but if remove, must be remove next
        ),
        "opPrecondition": lambda op: BoolLit(True),
        "stateTypeHint": SetT(OpaqueInt()),
        "opArgTypeHint": [EnumInt(), OpaqueInt()],
        "queryArgTypeHint": [OpaqueInt()],
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.Map(OpaqueInt(), lat.OrBool()),),
    },
    "add_wins_set": {
        "ll_name": "sequential1_clock",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)),  # if first command is insert
            Eq(arg2[0], IntLit(1)), # second command must be insert
            BoolLit(True),  # second can be insert or remove
        ),
        "opPrecondition": lambda op: Ge(op[-1], IntLit(1)),
        "stateTypeHint": SetT(OpaqueInt()),
        "opArgTypeHint": [EnumInt(), OpaqueInt(), ClockInt()],
        "queryArgTypeHint": [OpaqueInt()],
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.Map(OpaqueInt(), lat.MaxInt(ClockInt())),lat.Map(OpaqueInt(), lat.MaxInt(ClockInt()))),
    },
    "remove_wins_set": {
        "ll_name": "sequential1_clock",
        "inOrder": lambda arg1, arg2: Ite(
            Eq(arg1[0], IntLit(1)),  # if first command is insert
            BoolLit(True),  # second can be insert or remove
            Not(Eq(arg2[0], IntLit(1))),  # but if remove, must be remove next
        ),
        "opPrecondition": lambda op: Ge(op[-1], IntLit(1)),
        "stateTypeHint": SetT(OpaqueInt()),
        "opArgTypeHint": [EnumInt(), OpaqueInt(), ClockInt()],
        "queryArgTypeHint": [OpaqueInt()],
        "queryRetTypeHint": EnumInt(),
        "fixedLatticeType": (lat.Map(OpaqueInt(), lat.MaxInt(ClockInt())),lat.Map(OpaqueInt(), lat.MaxInt(ClockInt()))),
    },
    "grow_only_counter": {
        "ll_name": "sequential2",
        "inOrder": lambda arg1, arg2: And(
            Eq(arg1[0], IntLit(1)),
            Eq(arg2[0], IntLit(1))
        ),
        "opPrecondition": lambda op: Eq(op[0], IntLit(1)),
        "stateTypeHint": Int(),
        "opArgTypeHint": [EnumInt(), NodeIDInt()],
        "queryArgTypeHint": [],
        "queryRetTypeHint": Int(),
        "nonIdempotent": True,
        "fixedLatticeType": (lat.Map(NodeIDInt(), lat.MaxInt(Int())),),
    },
    "general_counter": {
        "ll_name": "sequential2",
        "inOrder": lambda arg1, arg2: BoolLit(True),
        "opPrecondition": lambda op: BoolLit(True),
        "stateTypeHint": Int(),
        "opArgTypeHint": [EnumInt(), NodeIDInt()],
        "queryArgTypeHint": [],
        "queryRetTypeHint": Int(),
        "nonIdempotent": True,
        "fixedLatticeType": (lat.Map(NodeIDInt(), lat.MaxInt(Int())),lat.Map(NodeIDInt(), lat.MaxInt(Int()))),
    }
}

def has_node_id(tup):
    for v in tup:
        if v.has_node_id():
            return True
    return False

def increasing_depth_structures(underlying):
    base_depth = 1
    while True:
        # we synthesize structures of complexity base_depth + 1
        all_structures = underlying(base_depth)
        filtered_structures = all_structures
        if nonIdempotent:
            filtered_structures = filter(has_node_id, all_structures)
        for struct in filtered_structures:
            yield (base_depth, struct)
        base_depth += 1

if __name__ == "__main__":
    mode = sys.argv[1]
    bench = sys.argv[2]
    fixed_structure = len(sys.argv) >= 4 and sys.argv[3] == "fixed"
    first_n = int(sys.argv[3].split("first_")[1]) if (len(sys.argv) >= 4 and sys.argv[3].startswith("first_")) else None
    reps = int(sys.argv[3].split("repeat_")[1]) if (len(sys.argv) >= 4 and sys.argv[3].startswith("repeat_")) else 1

    if bench == "all":
        benches = list(benchmarks.keys())
    else:
        benches = [bench]

    useOpList = True
    if mode == "synth-unbounded":
        useOpList = False

    bounded_bench_str = "bounded-pruning" if useOpList else "direct-unbounded"

    bench_file = open(f"results-{bench}-{bounded_bench_str}.csv", "w") if first_n == None else contextlib.nullcontext()
    with bench_file as report:
        for bench in benches:
            bench_data = benchmarks[bench]

            filename = f"tests/{bench_data['ll_name']}.ll"
            fnNameBase = "test"
            loopsFile = f"tests/{bench_data['ll_name']}.loops"
            cvcPath = "cvc5"

            nonIdempotent = "nonIdempotent" in bench_data and bench_data["nonIdempotent"]

            for rep in range(reps):
                structure_generator = increasing_depth_structures(
                    (lambda base_depth: lat.gen_structures(base_depth))
                    if not fixed_structure
                    else
                    (lambda _: [bench_data["fixedLatticeType"]])
                )

                start_time = time()
                report_file = f"search-{bench}-{rep}-{bounded_bench_str}-first_{first_n}.csv"

                clock_augmented_order = bench_data["inOrder"]
                if bench_data["opArgTypeHint"] and bench_data["opArgTypeHint"][-1] == ClockInt():
                    orig_order = clock_augmented_order
                    clock_augmented_order = lambda arg1, arg2: Ite(
                        Lt(arg1[-1], arg2[-1]),  # if clocks in order
                        BoolLit(True),
                        Ite(
                            Eq(arg1[-1], arg2[-1]), # if clocks concurrent
                            orig_order(arg1, arg2),
                            BoolLit(False), # clocks out of order
                        )
                    )

                (result_type, result_fns) = search_crdt_structures(
                    initState,
                    grammarStateInvariant,
                    grammarSupportedCommand,
                    clock_augmented_order,
                    bench_data["opPrecondition"],
                    grammar,
                    grammarQuery,
                    grammarEquivalence,
                    targetLang,
                    synthesize,
                    filename, fnNameBase, loopsFile, cvcPath, useOpList,
                    structure_generator,
                    reportFile=report_file,
                    stateTypeHint=bench_data["stateTypeHint"],
                    opArgTypeHint=bench_data["opArgTypeHint"],
                    queryArgTypeHint=bench_data["queryArgTypeHint"],
                    queryRetTypeHint=bench_data["queryRetTypeHint"],
                    maxThreads=1 if fixed_structure else mp.cpu_count(),
                    upToUid=first_n,
                    exitFirstSuccess=first_n == None,
                )
                end_time = time()

                if first_n == None:
                    print(f"{bench} (repetition {rep}) took {end_time - start_time} seconds\n\n")
                    results_code = ";".join([c.toRosette().replace("\n", " ") for c in result_fns])
                    report.write(f"{bench},{rep},{end_time - start_time},\"{result_type}\",\"{results_code}\"\n")
                    report.flush()
                else:
                    with open(report_file, newline='') as csvfile:
                        report_reader = csv.reader(csvfile)
                        times = sorted([float(row[1]) for row in report_reader])
                        with open(f"benchmarks-{bench}-{bounded_bench_str}-first_{first_n}-distribution.csv", "w") as distribution_file:
                            distribution_file.write(f"time,percent\n")
                            for (i, time) in enumerate(times):
                                percent = (i + 1) / len(times)
                                distribution_file.write(f"{time},{percent}\n")
