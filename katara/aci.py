import os

from metalift.analysis import analyze
from metalift.ir import *
from metalift.smt_util import toSMT

from llvmlite.binding import ValueRef

import typing
from typing import Any

import subprocess
from metalift.synthesize_cvc5 import generateAST, toExpr


def check_aci(filename: str, fnNameBase: str, loopsFile: str, cvcPath: str) -> None:
    basename = os.path.splitext(os.path.basename(filename))[0]

    # begin state transition
    wrapBeforeState: Any = None
    wrapAfterState: Any = None
    wrapTransitionArgs: Any = None
    nextVc: Any = None

    def summaryWrapStateTransition(ps: MLInst) -> typing.Tuple[Expr, typing.List[Expr]]:
        nonlocal wrapBeforeState
        nonlocal wrapAfterState
        nonlocal wrapTransitionArgs
        nonlocal nextVc

        origReturn = ps.operands[2]
        origArgs = ps.operands[3:]
        wrapTransitionArgs = origArgs[1:]

        beforeState = typing.cast(ValueRef, origArgs[0])
        afterState = typing.cast(ValueRef, origReturn)

        prevAfterState = wrapAfterState

        wrapBeforeState = beforeState
        wrapAfterState = afterState

        if not nextVc:
            finalState_0 = Var(
                fnNameBase + "_next_state" + "_0_cmd1_" + wrapAfterState.name,
                parseTypeRef(wrapAfterState.type),
            )
            finalState_1 = Var(
                fnNameBase + "_next_state" + "_1_cmd1_" + wrapAfterState.name,
                parseTypeRef(wrapAfterState.type),
            )
            nextVc = Eq(finalState_0, finalState_1)

        return (
            Implies(Eq(prevAfterState, beforeState), nextVc)
            if prevAfterState
            else nextVc,
            list(ps.operands[2:]),  # type: ignore
        )

    (
        vcVarsStateTransition_0_cmd0,
        _,
        predsStateTransition_0_cmd0,
        nextVc,
        _,
    ) = analyze(
        filename,
        fnNameBase + "_next_state",
        loopsFile,
        wrapSummaryCheck=summaryWrapStateTransition,
        fnNameSuffix="_0_cmd0",
    )

    beforeState_0_cmd0 = Var(
        fnNameBase + "_next_state" + "_0_cmd0_" + wrapBeforeState.name,
        parseTypeRef(wrapBeforeState.type),
    )
    wrapAfterState = Var(
        fnNameBase + "_next_state" + "_0_cmd0_" + wrapAfterState.name,
        parseTypeRef(wrapAfterState.type),
    )
    afterState_0_cmd0 = wrapAfterState
    transitionArgs_0_cmd0 = [
        Var(fnNameBase + "_next_state" + "_0_cmd0_" + v.name, parseTypeRef(v.type))
        for v in wrapTransitionArgs
    ]

    (
        vcVarsStateTransition_0_cmd1,
        _,
        predsStateTransition_0_cmd1,
        nextVc,
        _,
    ) = analyze(
        filename,
        fnNameBase + "_next_state",
        loopsFile,
        wrapSummaryCheck=summaryWrapStateTransition,
        fnNameSuffix="_0_cmd1",
    )

    beforeState_0_cmd1 = Var(
        fnNameBase + "_next_state" + "_0_cmd1_" + wrapBeforeState.name,
        parseTypeRef(wrapBeforeState.type),
    )
    wrapAfterState = Var(
        fnNameBase + "_next_state" + "_0_cmd1_" + wrapAfterState.name,
        parseTypeRef(wrapAfterState.type),
    )
    afterState_0_cmd1 = wrapAfterState
    transitionArgs_0_cmd1 = [
        Var(fnNameBase + "_next_state" + "_0_cmd1_" + v.name, parseTypeRef(v.type))
        for v in wrapTransitionArgs
    ]

    wrapAfterState = None

    (
        vcVarsStateTransition_1_cmd0,
        _,
        predsStateTransition_1_cmd0,
        nextVc,
        _,
    ) = analyze(
        filename,
        fnNameBase + "_next_state",
        loopsFile,
        wrapSummaryCheck=summaryWrapStateTransition,
        fnNameSuffix="_1_cmd0",
    )

    beforeState_1_cmd0 = Var(
        fnNameBase + "_next_state" + "_1_cmd0_" + wrapBeforeState.name,
        parseTypeRef(wrapBeforeState.type),
    )
    wrapAfterState = Var(
        fnNameBase + "_next_state" + "_1_cmd0_" + wrapAfterState.name,
        parseTypeRef(wrapAfterState.type),
    )
    afterState_1_cmd0 = wrapAfterState
    transitionArgs_1_cmd0 = [
        Var(fnNameBase + "_next_state" + "_1_cmd0_" + v.name, parseTypeRef(v.type))
        for v in wrapTransitionArgs
    ]

    (
        vcVarsStateTransition_1_cmd1,
        _,
        predsStateTransition_1_cmd1,
        nextVc,
        _,
    ) = analyze(
        filename,
        fnNameBase + "_next_state",
        loopsFile,
        wrapSummaryCheck=summaryWrapStateTransition,
        fnNameSuffix="_1_cmd1",
    )

    beforeState_1_cmd1 = Var(
        fnNameBase + "_next_state" + "_1_cmd1_" + wrapBeforeState.name,
        parseTypeRef(wrapBeforeState.type),
    )
    wrapAfterState = Var(
        fnNameBase + "_next_state" + "_1_cmd1_" + wrapAfterState.name,
        parseTypeRef(wrapAfterState.type),
    )
    afterState_1_cmd1 = wrapAfterState
    transitionArgs_1_cmd1 = [
        Var(fnNameBase + "_next_state" + "_1_cmd1_" + v.name, parseTypeRef(v.type))
        for v in wrapTransitionArgs
    ]

    combinedVCVars = (
        vcVarsStateTransition_0_cmd0.union(vcVarsStateTransition_0_cmd1)
        .union(vcVarsStateTransition_1_cmd0)
        .union(vcVarsStateTransition_1_cmd1)
    )

    combinedPreds = (
        predsStateTransition_0_cmd0
        + predsStateTransition_0_cmd1
        + predsStateTransition_1_cmd0
        + predsStateTransition_1_cmd1
    )

    combinedVC = Implies(
        And(
            Eq(beforeState_0_cmd0, beforeState_1_cmd0),
            And(
                *[
                    Eq(a1, a2)
                    for a1, a2 in zip(transitionArgs_0_cmd0, transitionArgs_1_cmd1)
                ]
            ),
            And(
                *[
                    Eq(a1, a2)
                    for a1, a2 in zip(transitionArgs_0_cmd1, transitionArgs_1_cmd0)
                ]
            ),
        ),
        nextVc,
    )
    # end state transition

    toSMT(
        [],
        combinedVCVars,
        [],
        combinedPreds,
        combinedVC,
        "./synthesisLogs/aci-test.smt",
        [],
        [],
    )

    procVerify = subprocess.run(
        [
            cvcPath,
            "--lang=smt",
            "--produce-models",
            "--tlimit=100000",
            "./synthesisLogs/aci-test.smt",
        ],
        stdout=subprocess.PIPE,
    )

    procOutput = procVerify.stdout
    resultVerify = procOutput.decode("utf-8").split("\n")

    def lookup_var(v: Expr) -> Expr:
        for line in resultVerify:
            if line.startswith("(define-fun " + v.args[0] + " "):
                return toExpr(generateAST(line)[0][4], [], [], {}, {})
        raise Exception("Could not find variable " + v.args[0])

    if resultVerify[0] == "sat" or resultVerify[0] == "unknown":
        print("Counterexample Found")
        print(f"Command 1: {[lookup_var(v) for v in transitionArgs_0_cmd0]}")
        print(f"Command 2: {[lookup_var(v) for v in transitionArgs_0_cmd1]}")
        print(f"Initial State: {lookup_var(beforeState_0_cmd0)}")
        print()
        print(f"After Command 1:")
        print(f"Actor 1: {lookup_var(afterState_0_cmd0)}")
        print(f"Actor 2: {lookup_var(afterState_1_cmd0)}")
        print()
        print(f"After Command 2:")
        print(f"Actor 1: {lookup_var(afterState_0_cmd1)}")
        print(f"Actor 2: {lookup_var(afterState_1_cmd1)}")
    else:
        print("Actor is commutative")
