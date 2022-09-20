from katara import lattices
from katara.lattices import Lattice
from metalift.ir import *

import typing
from typing import Union, Dict
from llvmlite.binding import ValueRef

equality_supported_types = [Bool(), Int(), ClockInt(), EnumInt(), OpaqueInt()]
comparison_supported_types = [Int(), ClockInt(), OpaqueInt()]


def get_expansions(
    input_types: typing.List[Type],
    available_types: typing.List[Type],
    out_types: typing.List[Type],
    allow_node_id_reductions: bool = False,
) -> Dict[Type, typing.List[typing.Callable[[typing.Callable[[Type], Expr]], Expr]]]:
    out: Dict[
        Type, typing.List[typing.Callable[[typing.Callable[[Type], Expr]], Expr]]
    ] = {
        Bool(): [
            lambda get: BoolLit(False),
            lambda get: BoolLit(True),
            lambda get: And(get(Bool()), get(Bool())),
            lambda get: Or(get(Bool()), get(Bool())),
            lambda get: Not(get(Bool())),
            *[
                (lambda t: lambda get: Eq(get(t), get(t)))(t)
                for t in equality_supported_types
            ],
            *[
                (lambda t: lambda get: Gt(get(t), get(t)))(t)
                for t in comparison_supported_types
            ],
            *[
                (lambda t: lambda get: Ge(get(t), get(t)))(t)
                for t in comparison_supported_types
            ],
        ],
    }

    def gen_set_ops(t: Type) -> None:
        out[SetT(t)] = [
            lambda get: Call("set-minus", SetT(t), get(SetT(t)), get(SetT(t))),
            lambda get: Call("set-union", SetT(t), get(SetT(t)), get(SetT(t))),
            lambda get: Call("set-insert", SetT(t), get(t), get(SetT(t))),
        ]

        out[Bool()].append(lambda get: Eq(get(SetT(t)), get(SetT(t))))
        out[Bool()].append(lambda get: Eq(get(SetT(t)), Call("set-create", SetT(t))))
        out[Bool()].append(
            lambda get: Call("set-subset", Bool(), get(SetT(t)), get(SetT(t)))
        )
        out[Bool()].append(lambda get: Call("set-member", Bool(), get(t), get(SetT(t))))

    for t in equality_supported_types:
        if t in input_types:
            gen_set_ops(t)
        else:
            out[SetT(t)] = []

        if SetT(t) in out_types:
            out[SetT(t)] += [
                ((lambda t: lambda get: Call("set-create", SetT(t)))(t))
                if t in input_types
                else ((lambda t: lambda get: Call("set-create", SetT(get(t).type)))(t)),
                (lambda t: lambda get: Call("set-singleton", SetT(t), get(t)))(t),
            ]

    def gen_map_ops(k: Type, v: Type, allow_zero_create: bool) -> None:
        if MapT(k, v) in out_types:
            if MapT(k, v) not in out:
                out[MapT(k, v)] = []
            out[MapT(k, v)] += [
                (lambda get: Call("map-create", MapT(k, v)))
                if allow_zero_create
                else (lambda get: Call("map-create", MapT(get(k).type, v))),
                lambda get: Call("map-singleton", MapT(k, v), get(k), get(v)),
            ]

        if v not in out:
            out[v] = []

        if MapT(k, v) in input_types:
            if v.erase() == Int():
                out[v] += [
                    lambda get: Call("map-get", v, get(MapT(k, v)), get(k), Lit(0, v)),
                ]

                if k == NodeIDInt() and allow_node_id_reductions:
                    merge_a = Var("merge_into", v)
                    merge_b = Var("merge_v", v)

                    if v == Int():
                        out[v] += [
                            lambda get: Call(
                                "reduce_int",
                                v,
                                Call("map-values", ListT(v), get(MapT(k, v))),
                                Lambda(
                                    v,
                                    Add(merge_a, merge_b),
                                    merge_b,
                                    merge_a,
                                ),
                                IntLit(0),
                            )
                        ]
            elif v == Bool():
                out[v] += [
                    lambda get: Call(
                        "map-get",
                        v,
                        get(MapT(k, v)),
                        get(k),
                        Choose(BoolLit(False), BoolLit(True)),
                    ),
                ]

                if k == NodeIDInt() and allow_node_id_reductions:
                    merge_a = Var("merge_into", v)
                    merge_b = Var("merge_v", v)

                    out[v] += [
                        lambda get: Call(
                            "reduce_bool",
                            v,
                            Call("map-values", ListT(v), get(MapT(k, v))),
                            Lambda(
                                v,
                                Or(merge_a, merge_b),
                                merge_b,
                                merge_a,
                            ),
                            BoolLit(False),
                        ),
                        lambda get: Call(
                            "reduce_bool",
                            v,
                            Call("map-values", ListT(v), get(MapT(k, v))),
                            Lambda(
                                v,
                                And(merge_a, merge_b),
                                merge_b,
                                merge_a,
                            ),
                            BoolLit(True),
                        ),
                    ]
            elif v.name == "Map":
                out[v] += [
                    lambda get: Call(
                        "map-get", v, get(MapT(k, v)), get(k), Call("map-create", v)
                    ),
                ]
            else:
                raise Exception("NYI")

    for t in available_types:
        if t.name == "Map":
            gen_map_ops(t.args[0], t.args[1], t.args[0] in input_types)

    if Int() in input_types:
        if Int() not in out:
            out[Int()] = []
        out[Int()] += [
            lambda get: IntLit(0),
            lambda get: IntLit(1),
            lambda get: Add(get(Int()), get(Int())),
            lambda get: Sub(get(Int()), get(Int())),
        ]

    if EnumInt() in available_types:
        if EnumInt() not in out:
            out[EnumInt()] = []
        out[EnumInt()] += [(lambda i: lambda get: EnumIntLit(i))(i) for i in range(2)]

    if ClockInt() in input_types:
        if ClockInt() not in out:
            out[ClockInt()] = []
        out[ClockInt()] += [lambda get: Lit(0, ClockInt())]

    return out


def all_node_id_gets(
    input: Expr,
    node_id: Expr,
    args: Dict[Type, Expr],
) -> typing.List[Expr]:
    if input.type.name == "Map":
        v = input.type.args[1]
        default: typing.Optional[Expr] = None
        if v.erase() == Int():
            default = Lit(0, v)
        elif v == Bool():
            default = Choose(BoolLit(False), BoolLit(True))
        elif v.name == "Map":
            default = Call("map-create", v)
        else:
            raise Exception("NYI")

        if input.type.args[0] == NodeIDInt():
            return [Call("map-get", v, input, node_id, default)]
        elif input.type.args[0] in args:
            return all_node_id_gets(
                Call("map-get", v, input, args[input.type.args[0]], default),
                node_id,
                args,
            )
        else:
            return []
    elif input.type.name == "Tuple":
        out = []
        for i in range(len(input.type.args)):
            out += all_node_id_gets(TupleGet(input, IntLit(i)), node_id, args)
        return out
    else:
        return []


def auto_grammar(
    out_type: typing.Optional[Type],
    depth: int,
    *inputs: Union[Expr, ValueRef],
    enable_ite: bool = False,
    allow_node_id_reductions: bool = False,
) -> Expr:
    if out_type and out_type.name == "Tuple":
        return Tuple(
            *[
                auto_grammar(
                    t,
                    depth,
                    *inputs,
                    enable_ite=enable_ite,
                    allow_node_id_reductions=allow_node_id_reductions,
                )
                for t in out_type.args
            ]
        )

    input_pool: Dict[Type, typing.List[Expr]] = {}

    def extract_inputs(input_type: Type, input: typing.Optional[Expr]) -> None:
        if input_type.name == "Tuple":
            for i, t in enumerate(input_type.args):
                if input != None:
                    extract_inputs(t, TupleGet(input, IntLit(i)))  # type: ignore
                else:
                    extract_inputs(t, None)
        else:
            if not input_type in input_pool:
                input_pool[input_type] = []
            if input != None:
                input_pool[input_type].append(input)  # type: ignore
            if input_type.name == "Set":
                extract_inputs(input_type.args[0], None)
            elif input_type.name == "Map":
                extract_inputs(input_type.args[0], None)
                extract_inputs(input_type.args[1], None)

    for input in inputs:
        input_type = parseTypeRef(input.type)
        extract_inputs(input_type, input)

    input_types = list(input_pool.keys())

    if out_type and out_type not in input_pool:
        extract_inputs(out_type, None)

    out_types = list(set(input_pool.keys()) - set(input_types))

    expansions = get_expansions(
        input_types, list(input_pool.keys()), out_types, allow_node_id_reductions
    )

    pool: Dict[Type, Expr] = {}
    for t, exprs in input_pool.items():
        zero_input_expansions = []
        if t in expansions:
            for e in expansions[t]:
                try:
                    zero_input_expansions.append(e(lambda t: dict()[t]))  # type: ignore
                except KeyError:
                    pass
        if (len(exprs) + len(zero_input_expansions)) > 0:
            pool[t] = Choose(*exprs, *zero_input_expansions)

    for i in range(depth):
        next_pool = dict(pool)
        for t, expansion_list in expansions.items():
            new_elements = []
            for expansion in expansion_list:
                try:
                    new_elements.append(expansion(lambda t: pool[t]))
                except KeyError:
                    pass

            if (
                t in next_pool
                and isinstance(next_pool[t], Expr)
                and isinstance(next_pool[t], Choose)
            ):
                existing_set = set(next_pool[t].args)
                new_elements = [e for e in new_elements if e not in existing_set]

            if len(new_elements) > 0:
                if t in pool:
                    next_pool[t] = Choose(next_pool[t], *new_elements)
                else:
                    next_pool[t] = Choose(*new_elements)

        if enable_ite and Bool() in pool:
            for t in pool.keys():
                if t.name != "Set" and t.name != "Map":
                    next_pool[t] = Choose(
                        next_pool[t], Ite(pool[Bool()], pool[t], pool[t])
                    )

        pool = next_pool

    if out_type:
        return pool[out_type]
    else:
        return pool  # type: ignore


def expand_lattice_logic(*inputs: typing.Tuple[Expr, Lattice]) -> typing.List[Expr]:
    lattice_to_exprs: typing.Dict[Lattice, typing.List[Expr]] = {}
    for input, lattice in inputs:
        if lattice not in lattice_to_exprs:
            lattice_to_exprs[lattice] = []
        lattice_to_exprs[lattice].append(input)

    next_pool = dict(lattice_to_exprs)
    for lattice in lattice_to_exprs.keys():
        if isinstance(lattice, lattices.Map):
            merge_a = Var("merge_a", lattice.valueType.ir_type())
            merge_b = Var("merge_b", lattice.valueType.ir_type())
            for value in lattice_to_exprs[lattice]:
                value_max = Call(  # does the remove set have any concurrent values?
                    "reduce_bool"
                    if lattice.valueType.ir_type() == Bool()
                    else "reduce_int",
                    lattice.valueType.ir_type(),
                    Call("map-values", ListT(lattice.valueType.ir_type()), value),
                    Lambda(
                        lattice.valueType.ir_type(),
                        lattice.valueType.merge(merge_a, merge_b),
                        merge_a,
                        merge_b,
                    ),
                    lattice.valueType.bottom(),
                )

                if lattice.valueType not in next_pool:
                    next_pool[lattice.valueType] = []
                if value_max not in next_pool[lattice.valueType]:
                    next_pool[lattice.valueType].append(value_max)

    lattice_to_exprs = next_pool
    next_pool = dict(lattice_to_exprs)

    for lattice in lattice_to_exprs.keys():
        choices = Choose(*lattice_to_exprs[lattice])
        lattice_to_exprs[lattice].append(lattice.merge(choices, choices))

    lattice_to_exprs = next_pool

    return [Choose(*lattice_to_exprs[lattice]) for lattice in lattice_to_exprs.keys()]
