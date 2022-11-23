import sys

from metalift.analysis_new import VariableTracker, analyze as analyze_new
from metalift.ir import *
from metalift.smt_util import toSMT

import subprocess
from metalift.synthesize_cvc5 import generateAST, toExpr


def check_aci(filename: str, fnNameBase: str, loopsFile: str, cvcPath: str) -> None:
    check_a(filename, fnNameBase, loopsFile, cvcPath)
    check_i(filename, fnNameBase, loopsFile, cvcPath)


def check_a(filename: str, fnNameBase: str, loopsFile: str, cvcPath: str) -> None:
    state_transition_analysis = analyze_new(
        filename, fnNameBase + "_next_state", loopsFile
    )

    tracker = VariableTracker()

    initial_state = tracker.variable(
        "initial_state", state_transition_analysis.arguments[0].type
    )

    op1_group = tracker.group("op1")
    op1 = [
        op1_group.variable(v.name(), v.type)
        for v in state_transition_analysis.arguments[1:]
    ]

    op2_group = tracker.group("op2")
    op2 = [
        op2_group.variable(v.name(), v.type)
        for v in state_transition_analysis.arguments[1:]
    ]

    afterState_0_op1 = tracker.variable(
        "afterState_0_op1", state_transition_analysis.arguments[0].type
    )
    afterState_0_op2 = tracker.variable(
        "afterState_0_op2", state_transition_analysis.arguments[0].type
    )

    afterState_1_op2 = tracker.variable(
        "afterState_1_op2", state_transition_analysis.arguments[0].type
    )
    afterState_1_op1 = tracker.variable(
        "afterState_1_op1", state_transition_analysis.arguments[0].type
    )

    vc = state_transition_analysis.call(initial_state, *op1)(
        tracker,
        lambda obj0_after_op1: Implies(
            Eq(obj0_after_op1, afterState_0_op1),
            state_transition_analysis.call(obj0_after_op1, *op2)(
                tracker,
                lambda obj0_after_op2: Implies(
                    Eq(obj0_after_op2, afterState_0_op2),
                    state_transition_analysis.call(initial_state, *op2)(
                        tracker,
                        lambda obj1_after_op2: Implies(
                            Eq(obj1_after_op2, afterState_1_op2),
                            state_transition_analysis.call(obj1_after_op2, *op1)(
                                tracker,
                                lambda obj1_after_op1: Implies(
                                    Eq(obj1_after_op1, afterState_1_op1),
                                    Eq(obj0_after_op2, obj1_after_op1),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    toSMT(
        [],
        set(tracker.all()),
        [],
        [],
        vc,
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
        print("Counterexample Found for Commutativity Check")
        print(f"Operation 1: {[lookup_var(v) for v in op1]}")
        print(f"Operation 2: {[lookup_var(v) for v in op2]}")
        print(f"Initial State: {lookup_var(initial_state)}")
        print()
        print(f"Actor 1 (after op 1): {lookup_var(afterState_0_op1)}")
        print(f"Actor 1 (after op 1 + 2): {lookup_var(afterState_0_op2)}")
        print()
        print(f"Actor 2 (after op 2): {lookup_var(afterState_1_op2)}")
        print(f"Actor 2 (after op 2 + 1): {lookup_var(afterState_1_op1)}")
    else:
        print("Actor is commutative")


def check_i(filename: str, fnNameBase: str, loopsFile: str, cvcPath: str) -> None:
    state_transition_analysis = analyze_new(
        filename, fnNameBase + "_next_state", loopsFile
    )

    tracker = VariableTracker()

    initial_state = tracker.variable(
        "initial_state", state_transition_analysis.arguments[0].type
    )
    
    op_group = tracker.group("op")
    op = [
        op_group.variable(v.name(), v.type)
        for v in state_transition_analysis.arguments[1:]  
    ]
    
    afterState_op = tracker.variable(
        "afterState_op", state_transition_analysis.arguments[0].type
    )
    afterState_op_op = tracker.variable(
        "afterState_op_op", state_transition_analysis.arguments[0].type
    )
    
    vc = state_transition_analysis.call(initial_state, *op)(
        tracker,
        lambda obj0_after_op: Implies(
            Eq(obj0_after_op, afterState_op),
            state_transition_analysis.call(obj0_after_op, *op)(
                tracker,
                lambda obj0_after_op_op: Implies(
                    Eq(obj0_after_op_op, afterState_op_op),
                    Eq(obj0_after_op, obj0_after_op_op)
                )
            )
        )
    )
    
    toSMT(
        [],
        set(tracker.all()),
        [],
        [],
        vc,
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
        print("Counterexample Found for Idempotence Check")
        print(f"Operation: {[lookup_var(v) for v in op]}")
        print(f"Initial State: {lookup_var(initial_state)}")
        print()
        print(f"After 1 operation: {lookup_var(afterState_op)}")
        print(f"After 2 operations (op + op): {lookup_var(afterState_op_op)}")
    else:
        print("Actor is Idempotent") 
    
    pass


if __name__ == "__main__":
    filename = f"tests/{sys.argv[1]}.ll"
    fnNameBase = "test"
    loopsFile = f"tests/{sys.argv[1]}.loops"
    cvcPath = "cvc5"

    check_aci(filename, fnNameBase, loopsFile, cvcPath)
