import os

from metalift.analysis_new import VariableTracker, analyze
from metalift.ir import *

import typing
from typing import Callable, Union, Protocol

from metalift.synthesis_common import SynthesisFailed, VerificationFailed


def observeEquivalence(
    inputState: Expr, synthState: Expr, queryParams: typing.List[Var]
) -> Expr:
    return Call("equivalence", Bool(), inputState, synthState, *queryParams)


def opsListInvariant(
    fnNameBase: str, synthState: Expr, synthStateType: Type, opType: Type
) -> Expr:
    return And(
        Eq(
            Call(
                "apply_state_transitions",
                synthStateType,
                TupleGet(synthState, IntLit(len(synthStateType.args) - 1)),
                Var(
                    f"{fnNameBase}_next_state",
                    FnT(synthStateType, synthStateType, *opType.args),
                ),
                Var(
                    f"{fnNameBase}_init_state",
                    FnT(synthStateType),
                ),
            ),
            synthState,
        ),
        Call(
            "ops_in_order",
            Bool(),
            TupleGet(synthState, IntLit(len(synthStateType.args) - 1)),
        ),
    )


def supportedCommand(synthState: Expr, args: typing.Any) -> Expr:
    return Call("supportedCommand", Bool(), synthState, *args)


def unpackOp(op: Expr) -> typing.List[Expr]:
    if op.type.name == "Tuple":
        return [TupleGet(op, IntLit(i)) for i in range(len(op.type.args))]
    else:
        return [op]


def opListAdditionalFns(
    synthStateType: Type,
    opType: Type,
    initState: Callable[[], Expr],
    inOrder: Callable[[typing.Any, typing.Any], Expr],
    opPrecondition: Callable[[typing.Any], Expr],
) -> typing.List[Union[FnDecl, FnDeclNonRecursive, Axiom]]:
    def list_length(l: Expr) -> Expr:
        return Call("list_length", Int(), l)

    def list_get(l: Expr, i: Expr) -> Expr:
        return Call("list_get", opType, l, i)

    def list_tail(l: Expr, i: Expr) -> Expr:
        return Call("list_tail", ListT(opType), l, i)

    data = Var("data", ListT(opType))
    next_state_fn = Var(
        "next_state_fn",
        FnT(
            synthStateType,
            synthStateType,
            *(opType.args if opType.name == "Tuple" else [opType]),
        ),
    )

    init_state_fn = Var("init_state_fn", FnT(synthStateType))

    reduce_fn = FnDecl(
        "apply_state_transitions",
        synthStateType,
        Ite(
            Eq(list_length(data), IntLit(0)),
            CallValue(init_state_fn),
            CallValue(
                next_state_fn,
                Call(
                    "apply_state_transitions",
                    synthStateType,
                    list_tail(data, IntLit(1)),
                    next_state_fn,
                    init_state_fn,
                ),
                *(
                    [
                        # TODO(shadaj): unnecessary cast
                        typing.cast(
                            Expr, TupleGet(list_get(data, IntLit(0)), IntLit(i))
                        )
                        for i in range(len(opType.args))
                    ]
                    if opType.name == "Tuple"
                    else [list_get(data, IntLit(0))]
                ),
            ),
        ),
        data,
        next_state_fn,
        init_state_fn,
    )

    next_op = Var("next_op", opType)
    ops_in_order_helper = FnDecl(
        "ops_in_order_helper",
        Bool(),
        And(
            opPrecondition(unpackOp(next_op)),
            Ite(
                Eq(list_length(data), IntLit(0)),
                BoolLit(True),
                And(
                    inOrder(unpackOp(list_get(data, IntLit(0))), unpackOp(next_op)),
                    Call(
                        "ops_in_order_helper",
                        Bool(),
                        list_get(data, IntLit(0)),
                        list_tail(data, IntLit(1)),
                    ),
                ),
            ),
        ),
        next_op,
        data,
    )

    ops_in_order = FnDecl(
        "ops_in_order",
        Bool(),
        Ite(
            Eq(list_length(data), IntLit(0)),
            BoolLit(True),
            Call(
                "ops_in_order_helper",
                Bool(),
                list_get(data, IntLit(0)),
                list_tail(data, IntLit(1)),
            ),
        ),
        data,
    )

    return [reduce_fn, ops_in_order_helper, ops_in_order]


class SynthesizeFun(Protocol):
    def __call__(
        self,
        basename: str,
        targetLang: typing.List[Union[FnDecl, FnDeclNonRecursive, Axiom]],
        vars: typing.Set[Var],
        invAndPs: typing.List[Synth],
        preds: Union[str, typing.List[Expr]],
        vc: Expr,
        loopAndPsInfo: typing.List[Expr],
        cvcPath: str = "cvc5",
        uid: int = 0,
        noVerify: bool = False,
        unboundedInts: bool = False,
        optimize_vc_equality: bool = False,
        listBound: int = 2,
        log: bool = True,
    ) -> typing.List[FnDecl]:
        ...


def synthesize_crdt(
    filename: str,
    fnNameBase: str,
    loopsFile: str,
    cvcPath: str,
    synthStateType: Type,
    initState: Callable[[], Expr],
    grammarStateInvariant: Callable[[Expr, int, int], Expr],
    grammarSupportedCommand: Callable[[Expr, typing.Any, int, int], Expr],
    inOrder: Callable[[typing.Any, typing.Any], Expr],
    opPrecondition: Callable[[typing.Any], Expr],
    grammar: Callable[[Expr, typing.List[Var], int], Expr],
    grammarQuery: Callable[[str, typing.List[Var], Type, int], Synth],
    grammarEquivalence: Callable[[Expr, Expr, typing.List[Var], int], Expr],
    targetLang: Callable[[], typing.List[Union[FnDecl, FnDeclNonRecursive, Axiom]]],
    synthesize: SynthesizeFun,
    stateTypeHint: typing.Optional[Type] = None,
    opArgTypeHint: typing.Optional[typing.List[Type]] = None,
    queryArgTypeHint: typing.Optional[typing.List[Type]] = None,
    queryRetTypeHint: typing.Optional[Type] = None,
    uid: int = 0,
    unboundedInts: bool = True,
    useOpList: bool = False,
    listBound: int = 1,
    baseDepth: int = 2,
    invariantBoost: int = 0,
    log: bool = True,
    skipSynth: bool = False,
) -> typing.List[FnDecl]:
    basename = os.path.splitext(os.path.basename(filename))[0]

    tracker = VariableTracker()

    state_transition_analysis = analyze(
        filename,
        fnNameBase + "_next_state",
        loopsFile,
    )

    query_analysis = analyze(
        filename,
        fnNameBase + "_response",
        loopsFile,
    )

    origSynthStateType = synthStateType

    op_arg_types = (
        [v.type for v in state_transition_analysis.arguments[1:]]
        if opArgTypeHint is None
        else opArgTypeHint
    )
    opType = TupleT(*op_arg_types) if len(op_arg_types) > 1 else op_arg_types[1]

    if useOpList:
        synthStateType = TupleT(*synthStateType.args, ListT(opType))

    queryParameterTypes = (
        [v.type for v in query_analysis.arguments[1:]]
        if queryArgTypeHint is None
        else queryArgTypeHint
    )

    def supportedCommandWithList(synthState: Expr, args: typing.Any) -> Expr:
        return And(
            opPrecondition(args),
            Ite(
                Eq(
                    Call(
                        "list_length",
                        Int(),
                        TupleGet(synthState, IntLit(len(synthStateType.args) - 1)),
                    ),
                    IntLit(0),
                ),
                BoolLit(True),
                inOrder(
                    unpackOp(
                        Call(
                            "list_get",
                            opType,
                            TupleGet(synthState, IntLit(len(synthStateType.args) - 1)),
                            IntLit(0),
                        )
                    ),
                    args,
                ),
            ),
        )

    seq_start_state = tracker.variable(
        "seq_start_state", state_transition_analysis.arguments[0].type
    )
    synth_start_state = tracker.variable("synth_start_state", synthStateType)
    equivalence_query_vars = [
        tracker.variable(
            f"start_state_query_var_{i}", query_analysis.arguments[i + 1].type
        )
        for i in range(len(query_analysis.arguments) - 1)
    ]

    synth_after_op = tracker.variable("synth_after_op", synthStateType)

    first_op_group = tracker.group("first_op")
    first_op_args = [
        first_op_group.variable(v.name(), t)
        for v, t in zip(state_transition_analysis.arguments[1:], op_arg_types)
    ]

    second_op_group = tracker.group("second_op")
    second_op_args = [
        second_op_group.variable(v.name(), t)
        for v, t in zip(state_transition_analysis.arguments[1:], op_arg_types)
    ]

    vcStateTransition = state_transition_analysis.call(seq_start_state, *first_op_args)(
        tracker,
        lambda seq_after_op: Implies(
            And(
                observeEquivalence(
                    seq_start_state, synth_start_state, equivalence_query_vars
                ),
                *(
                    [
                        opsListInvariant(
                            fnNameBase, synth_start_state, synthStateType, opType
                        ),
                        supportedCommandWithList(synth_start_state, first_op_args),
                    ]
                    if useOpList
                    else [
                        opPrecondition(first_op_args),
                        supportedCommand(synth_start_state, first_op_args),
                    ]
                ),
                Eq(
                    synth_after_op,
                    Call(
                        f"{fnNameBase}_next_state",
                        synthStateType,
                        synth_start_state,
                        *first_op_args,
                    ),
                ),
            ),
            query_analysis.call(seq_start_state, *equivalence_query_vars)(
                tracker,
                lambda seqQueryResult: Implies(
                    Eq(
                        seqQueryResult,
                        Call(
                            f"{fnNameBase}_response",
                            seqQueryResult.type,
                            synth_start_state,
                            *equivalence_query_vars,
                        ),
                    ),
                    And(
                        observeEquivalence(
                            seq_after_op, synth_after_op, equivalence_query_vars
                        ),
                        query_analysis.call(seq_after_op, *equivalence_query_vars)(
                            tracker,
                            lambda seqQueryResult: Eq(
                                seqQueryResult,
                                Call(
                                    f"{fnNameBase}_response",
                                    seqQueryResult.type,
                                    synth_after_op,
                                    *equivalence_query_vars,
                                ),
                            ),
                        ),
                        *(
                            [
                                Implies(
                                    And(
                                        inOrder(first_op_args, second_op_args),
                                        opPrecondition(second_op_args),
                                    ),
                                    supportedCommand(synth_after_op, second_op_args),
                                )
                            ]
                            if not useOpList
                            else []
                        ),
                    ),
                ),
            ),
        ),
    )

    # define synthesis problem for state transition
    cur_state_param = Var("cur_state", synthStateType)

    op_arg_vars = [
        Var(v.name(), t)
        for v, t in zip(state_transition_analysis.arguments[1:], op_arg_types)
    ]

    stateTransitionSynthNode = grammar(
        cur_state_param,
        op_arg_vars,
        baseDepth,
    )

    invAndPsStateTransition = (
        [
            Synth(
                fnNameBase + "_next_state",
                Tuple(
                    # the grammar directly produces the tupled next state, unpack to tack on the op-list
                    *stateTransitionSynthNode.args,
                    Call(
                        "list_prepend",
                        ListT(opType),
                        Tuple(*op_arg_vars) if len(op_arg_vars) > 1 else op_arg_vars[0],
                        TupleGet(
                            cur_state_param,
                            IntLit(len(synthStateType.args) - 1),
                        ),
                    ),
                ),
                cur_state_param,
                *op_arg_vars,
            )
        ]
        if useOpList
        else [
            Synth(
                fnNameBase + "_next_state",
                stateTransitionSynthNode,
                cur_state_param,
                *op_arg_vars,
            )
        ]
    )
    # end state transition (in order)

    # begin query
    invAndPsQuery = [
        grammarQuery(
            query_analysis.name,
            [Var(query_analysis.arguments[0].name(), synthStateType)]
            + (
                [
                    Var(query_analysis.arguments[i + 1].name(), queryArgTypeHint[i])
                    for i in range(len(queryArgTypeHint))
                ]
                if queryArgTypeHint
                else query_analysis.arguments[1:]
            ),
            query_analysis.return_type
            if queryRetTypeHint is None
            else queryRetTypeHint,
            baseDepth,
        )
    ]
    # end query

    # begin init state
    initState_analysis = analyze(
        filename,
        fnNameBase + "_init_state",
        loopsFile,
    )

    synthInitState = tracker.variable("synth_init_state", synthStateType)

    init_op_arg_vars = []
    for i, typ in enumerate(op_arg_types):
        init_op_arg_vars.append(tracker.variable(f"init_op_arg_{i}", typ))

    queryParamVars = [
        tracker.variable(
            f"init_state_equivalence_query_param_{i}",
            query_analysis.arguments[i + 1].type,
        )
        for i in range(len(query_analysis.arguments) - 1)
    ]

    vcInitState = initState_analysis.call()(
        tracker,
        lambda seqInitialState: Implies(
            Eq(synthInitState, Call(f"{fnNameBase}_init_state", synthStateType)),
            And(
                observeEquivalence(seqInitialState, synthInitState, queryParamVars),
                query_analysis.call(seqInitialState, *queryParamVars)(
                    tracker,
                    lambda seqQueryResult: Eq(
                        seqQueryResult,
                        Call(
                            f"{fnNameBase}_response",
                            seqQueryResult.type,
                            synthInitState,
                            *queryParamVars,
                        ),
                    ),
                ),
                BoolLit(True)
                if useOpList
                else Implies(
                    opPrecondition(init_op_arg_vars),
                    supportedCommand(synthInitState, init_op_arg_vars),
                ),
            ),
        ),
    )

    initStateSynthNode = initState()
    invAndPsInitState = [
        Synth(
            fnNameBase + "_init_state",
            Tuple(
                *initStateSynthNode.args,
                Call("list_empty", ListT(opType)),
            )
            if useOpList
            else Tuple(
                *initStateSynthNode.args,
            ),
        )
    ]
    # end init state

    # begin equivalence
    inputStateForEquivalence = Var(
        "inputState",
        state_transition_analysis.arguments[0].type
        if stateTypeHint is None
        else stateTypeHint,
    )
    synthStateForEquivalence = Var("synthState", synthStateType)

    equivalenceQueryParams = [
        Var(f"equivalence_query_param_{i}", queryParameterTypes[i])
        for i in range(len(queryParameterTypes))
    ]

    invAndPsEquivalence = [
        Synth(
            "equivalence",
            And(
                grammarEquivalence(
                    inputStateForEquivalence,
                    synthStateForEquivalence,
                    equivalenceQueryParams,
                    baseDepth,
                ),
                *(
                    [
                        grammarStateInvariant(
                            synthStateForEquivalence, baseDepth, invariantBoost
                        )
                    ]
                    if not useOpList
                    else []
                ),
            ),
            inputStateForEquivalence,
            synthStateForEquivalence,
            *equivalenceQueryParams,
        )
    ]

    synthStateForSupported = Var(f"supported_synthState", synthStateType)
    argList = [
        Var(
            f"supported_arg_{i}",
            op_arg_types[i],
        )
        for i in range(len(op_arg_types))
    ]
    invAndPsSupported = (
        [
            Synth(
                "supportedCommand",
                grammarSupportedCommand(
                    synthStateForSupported, argList, baseDepth, invariantBoost
                ),
                synthStateForSupported,
                *argList,
            )
        ]
        if not useOpList
        else []
    )
    # end equivalence

    if log:
        print("====== synthesis")

    combinedVCVars = set(tracker.all())

    combinedInvAndPs = (
        invAndPsStateTransition
        + invAndPsQuery
        + invAndPsInitState
        + invAndPsEquivalence
        + invAndPsSupported
    )

    combinedVC = And(vcStateTransition, vcInitState)

    lang = targetLang()
    if useOpList:
        lang = lang + opListAdditionalFns(
            synthStateType, opType, initState, inOrder, opPrecondition
        )

    if skipSynth:
        return  # type: ignore

    try:
        out = synthesize(
            basename,
            lang,
            combinedVCVars,
            combinedInvAndPs,
            [],
            combinedVC,
            [*combinedInvAndPs],
            cvcPath,
            uid=uid,
            unboundedInts=unboundedInts,
            noVerify=useOpList,
            listBound=listBound,
            log=log,
        )
    except VerificationFailed:
        # direct synthesis mode
        print(
            f"#{uid}: CVC5 failed to verify synthesized design, increasing Rosette data structure bounds to",
            listBound + 1,
        )
        return synthesize_crdt(
            filename,
            fnNameBase,
            loopsFile,
            cvcPath,
            origSynthStateType,
            initState,
            grammarStateInvariant,
            grammarSupportedCommand,
            inOrder,
            opPrecondition,
            grammar,
            grammarQuery,
            grammarEquivalence,
            targetLang,
            synthesize,
            stateTypeHint=stateTypeHint,
            opArgTypeHint=opArgTypeHint,
            queryArgTypeHint=queryArgTypeHint,
            queryRetTypeHint=queryRetTypeHint,
            uid=uid,
            unboundedInts=unboundedInts,
            useOpList=useOpList,
            listBound=listBound + 1,
            baseDepth=baseDepth,
            invariantBoost=invariantBoost,
            log=log,
        )

    if useOpList:
        print(
            f"#{uid}: Synthesizing invariants for unbounded verification (Rosette structure/history bound: {listBound})"
        )
        equivalence_fn = [x for x in out if x.args[0] == "equivalence"][0]
        state_transition_fn = [
            x for x in out if x.args[0] == f"{fnNameBase}_next_state"
        ][0]
        query_fn = [x for x in out if x.args[0] == f"{fnNameBase}_response"][0]
        init_state_fn = [x for x in out if x.args[0] == f"{fnNameBase}_init_state"][0]

        equivalence_fn.args[3] = Var(
            equivalence_fn.args[3].args[0],
            TupleT(*equivalence_fn.args[3].type.args[:-1]),
        )

        equivalence_fn.args[1] = equivalence_fn.args[1].rewrite(
            {equivalence_fn.args[3].args[0]: equivalence_fn.args[3]}
        )

        state_transition_fn.args[2] = Var(
            state_transition_fn.args[2].args[0],
            TupleT(*state_transition_fn.args[2].type.args[:-1]),
        )

        # drop the op-list
        state_transition_fn.args[1] = Tuple(
            *[
                e.rewrite(
                    {state_transition_fn.args[2].args[0]: state_transition_fn.args[2]}
                )
                for e in state_transition_fn.args[1].args[:-1]
            ]
        )

        query_fn.args[2] = Var(
            query_fn.args[2].args[0], TupleT(*query_fn.args[2].type.args[:-1])
        )

        query_fn.args[1] = query_fn.args[1].rewrite(
            {query_fn.args[2].args[0]: query_fn.args[2]}
        )

        init_state_fn.args[1] = Tuple(*init_state_fn.args[1].args[:-1])

        try:
            # attempt to synthesize the invariants
            return synthesize_crdt(
                filename,
                fnNameBase,
                loopsFile,
                cvcPath,
                origSynthStateType,
                lambda: init_state_fn.args[1],  # type: ignore
                grammarStateInvariant,
                grammarSupportedCommand,
                inOrder,
                opPrecondition,
                lambda inState, args, _baseDepth: typing.cast(
                    Expr, state_transition_fn.args[1]
                ).rewrite(
                    {
                        cur_state_param.name(): inState,
                        **{orig.name(): new for orig, new in zip(op_arg_vars, args)},
                    }
                ),
                lambda _name, _args, _retT, _baseDepth: Synth(
                    query_fn.args[0], query_fn.args[1], *query_fn.args[2:]
                ),
                lambda a, b, _baseDepth, _invariantBoost: equivalence_fn.args[1],  # type: ignore
                targetLang,
                synthesize,
                stateTypeHint=stateTypeHint,
                opArgTypeHint=opArgTypeHint,
                queryArgTypeHint=queryArgTypeHint,
                queryRetTypeHint=queryRetTypeHint,
                uid=uid,
                unboundedInts=unboundedInts,
                useOpList=False,
                listBound=listBound,
                baseDepth=baseDepth,
                invariantBoost=invariantBoost,
                log=log,
            )
        except SynthesisFailed:
            try:
                # try to re-verify with a larger bound
                print(
                    f"#{uid}: re-verifying with history bound {listBound + 1} and attempting to re-synthesize invariants with deeper grammar"
                )
                return synthesize_crdt(
                    filename,
                    fnNameBase,
                    loopsFile,
                    cvcPath,
                    origSynthStateType,
                    lambda: init_state_fn.args[1],  # type: ignore
                    grammarStateInvariant,
                    grammarSupportedCommand,
                    inOrder,
                    opPrecondition,
                    lambda inState, args, _baseDepth: typing.cast(
                        Expr, state_transition_fn.args[1]
                    ).rewrite(
                        {
                            cur_state_param.name(): inState,
                            **{
                                orig.name(): new for orig, new in zip(op_arg_vars, args)
                            },
                        }
                    ),
                    lambda _name, args, _retT, _baseDepth: Synth(
                        query_fn.args[0], query_fn.args[1], *args
                    ),
                    lambda a, b, c, _baseDepth: equivalence_fn.args[1],  # type: ignore
                    targetLang,
                    synthesize,
                    stateTypeHint=stateTypeHint,
                    opArgTypeHint=opArgTypeHint,
                    queryArgTypeHint=queryArgTypeHint,
                    queryRetTypeHint=queryRetTypeHint,
                    uid=uid,
                    unboundedInts=unboundedInts,
                    useOpList=useOpList,
                    listBound=listBound + 1,
                    baseDepth=baseDepth,
                    invariantBoost=invariantBoost + 1,
                    log=log,
                )
            except SynthesisFailed:
                print(
                    f"#{uid}: could not synthesize invariants, re-synthesizing entire design with history bound {listBound + 1}"
                )
                return synthesize_crdt(
                    filename,
                    fnNameBase,
                    loopsFile,
                    cvcPath,
                    origSynthStateType,
                    initState,
                    grammarStateInvariant,
                    grammarSupportedCommand,
                    inOrder,
                    opPrecondition,
                    grammar,
                    grammarQuery,
                    grammarEquivalence,
                    targetLang,
                    synthesize,
                    stateTypeHint=stateTypeHint,
                    opArgTypeHint=opArgTypeHint,
                    queryArgTypeHint=queryArgTypeHint,
                    queryRetTypeHint=queryRetTypeHint,
                    uid=uid,
                    unboundedInts=unboundedInts,
                    useOpList=useOpList,
                    listBound=listBound + 1,
                    baseDepth=baseDepth,
                    invariantBoost=invariantBoost,
                    log=log,
                )
    else:
        return out
