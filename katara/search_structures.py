from __future__ import annotations

import multiprocessing as mp
import multiprocessing.pool
import queue
from time import time
import traceback
import typing

from katara.lattices import Lattice
from metalift.analysis import CodeInfo
from metalift import process_tracker
from metalift import ir
from metalift.ir import Expr, FnDecl
from katara.synthesis import SynthesizeFun, synthesize_crdt
from metalift.synthesis_common import SynthesisFailed

from typing import Any, Callable, Iterator, List, Optional, Tuple


def synthesize_crdt_e2e(
    queue: queue.Queue[
        Tuple[
            int,
            Any,
            int,
            Optional[typing.Union[str, List[FnDecl]]],
        ]
    ],
    synthStateStructure: List[Lattice],
    initState: Callable[[Any], Expr],
    grammarStateInvariant: Callable[[Expr, Any, int, int], Expr],
    grammarSupportedCommand: Callable[[Expr, Any, Any, int, int], Expr],
    inOrder: Callable[[Any, Any], Expr],
    opPrecondition: Callable[[Any], Expr],
    grammar: Callable[[Expr, List[ir.Var], Any, int], Expr],
    grammarQuery: Callable[[str, List[ir.Var], ir.Type, int], ir.Synth],
    grammarEquivalence: Callable[[Expr, Expr, List[ir.Var], int], Expr],
    targetLang: Callable[
        [], List[typing.Union[FnDecl, ir.FnDeclNonRecursive, ir.Axiom]]
    ],
    synthesize: SynthesizeFun,
    useOpList: bool,
    stateTypeHint: Optional[ir.Type],
    opArgTypeHint: Optional[List[ir.Type]],
    queryArgTypeHint: Optional[List[ir.Type]],
    queryRetTypeHint: Optional[ir.Type],
    baseDepth: int,
    filename: str,
    fnNameBase: str,
    loopsFile: str,
    cvcPath: str,
    uid: int,
) -> None:
    synthStateType = ir.TupleT(*[a.ir_type() for a in synthStateStructure])

    try:
        queue.put(
            (
                uid,
                synthStateStructure,
                baseDepth,
                synthesize_crdt(
                    filename,
                    fnNameBase,
                    loopsFile,
                    cvcPath,
                    synthStateType,
                    lambda: initState(synthStateStructure),
                    lambda s, baseDepth, invariantBoost: grammarStateInvariant(
                        s, synthStateStructure, baseDepth, invariantBoost
                    ),
                    lambda s, a, baseDepth, invariantBoost: grammarSupportedCommand(
                        s, a, synthStateStructure, baseDepth, invariantBoost
                    ),
                    inOrder,
                    opPrecondition,
                    lambda inState, args, baseDepth: grammar(
                        inState, args, synthStateStructure, baseDepth
                    ),
                    grammarQuery,
                    grammarEquivalence,
                    targetLang,
                    synthesize,
                    uid=uid,
                    useOpList=useOpList,
                    stateTypeHint=stateTypeHint,
                    opArgTypeHint=opArgTypeHint,
                    queryArgTypeHint=queryArgTypeHint,
                    queryRetTypeHint=queryRetTypeHint,
                    baseDepth=baseDepth,
                    log=False,
                ),
            )
        )
    except SynthesisFailed:
        queue.put((uid, synthStateStructure, baseDepth, None))
    except:
        queue.put((uid, synthStateStructure, baseDepth, traceback.format_exc()))


def search_crdt_structures(
    initState: Callable[[Any], Expr],
    grammarStateInvariant: Callable[[Expr, Any, int, int], Expr],
    grammarSupportedCommand: Callable[[Expr, Any, Any, int, int], Expr],
    inOrder: Callable[[Any, Any], Expr],
    opPrecondition: Callable[[Any], Expr],
    grammar: Callable[[Expr, List[ir.Var], Any, int], Expr],
    grammarQuery: Callable[[str, List[ir.Var], ir.Type, int], ir.Synth],
    grammarEquivalence: Callable[[Expr, Expr, List[ir.Var], int], Expr],
    targetLang: Callable[
        [], List[typing.Union[FnDecl, ir.FnDeclNonRecursive, ir.Axiom]]
    ],
    synthesize: SynthesizeFun,
    filename: str,
    fnNameBase: str,
    loopsFile: str,
    cvcPath: str,
    useOpList: bool,
    structureCandidates: Iterator[Tuple[int, Any]],
    reportFile: str,
    stateTypeHint: Optional[ir.Type] = None,
    opArgTypeHint: Optional[List[ir.Type]] = None,
    queryArgTypeHint: Optional[List[ir.Type]] = None,
    queryRetTypeHint: Optional[ir.Type] = None,
    maxThreads: int = mp.cpu_count(),
    upToUid: Optional[int] = None,
    exitFirstSuccess: bool = True,
) -> Tuple[Any, List[ir.Expr]]:
    q: queue.Queue[
        Tuple[int, Any, int, Optional[typing.Union[str, List[Expr]]]]
    ] = queue.Queue()
    queue_size = 0
    next_uid = 0

    next_res_type = None
    next_res = None

    start_times = {}

    try:
        with multiprocessing.pool.ThreadPool() as pool:
            with open(reportFile, "w") as report:
                while True:
                    while queue_size < (maxThreads // 2 if maxThreads > 1 else 1) and (
                        upToUid == None or next_uid < upToUid  # type: ignore
                    ):
                        next_structure_tuple = next(structureCandidates, None)
                        if next_structure_tuple is None:
                            break
                        else:
                            baseDepth, next_structure_type = next_structure_tuple

                            def error_callback(e: BaseException) -> None:
                                raise e

                            try:
                                synthStateType = ir.TupleT(
                                    *[a.ir_type() for a in next_structure_type]
                                )
                                synthesize_crdt(
                                    filename,
                                    fnNameBase,
                                    loopsFile,
                                    cvcPath,
                                    synthStateType,
                                    lambda: initState(next_structure_type),
                                    lambda s, baseDepth, invariantBoost: grammarStateInvariant(
                                        s,
                                        next_structure_type,
                                        baseDepth,
                                        invariantBoost,
                                    ),
                                    lambda s, a, baseDepth, invariantBoost: grammarSupportedCommand(
                                        s,
                                        a,
                                        next_structure_type,
                                        baseDepth,
                                        invariantBoost,
                                    ),
                                    inOrder,
                                    opPrecondition,
                                    lambda inState, args, baseDepth: grammar(
                                        inState,
                                        args,
                                        next_structure_type,
                                        baseDepth,
                                    ),
                                    grammarQuery,
                                    grammarEquivalence,
                                    targetLang,
                                    synthesize,
                                    uid=next_uid,
                                    useOpList=useOpList,
                                    stateTypeHint=stateTypeHint,
                                    opArgTypeHint=opArgTypeHint,
                                    queryArgTypeHint=queryArgTypeHint,
                                    queryRetTypeHint=queryRetTypeHint,
                                    baseDepth=baseDepth,
                                    log=False,
                                    skipSynth=True,
                                )
                            except KeyError as k:
                                print(k)
                                # this is due to a grammar not being able to find a value
                                continue

                            print(
                                f"Enqueueing #{next_uid} (structure: {next_structure_type}, base depth: {baseDepth})"
                            )
                            start_times[next_uid] = time()
                            pool.apply_async(
                                synthesize_crdt_e2e,
                                args=(
                                    q,
                                    next_structure_type,
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
                                    useOpList,
                                    stateTypeHint,
                                    opArgTypeHint,
                                    queryArgTypeHint,
                                    queryRetTypeHint,
                                    baseDepth,
                                    filename,
                                    fnNameBase,
                                    loopsFile,
                                    cvcPath,
                                    next_uid,
                                ),
                                error_callback=error_callback,
                            )
                            next_uid += 1
                            queue_size += 1

                    if queue_size == 0:
                        if exitFirstSuccess:
                            raise Exception("no more structures")
                        else:
                            break
                    else:
                        (ret_uid, next_res_type, baseDepth, next_res) = q.get(
                            block=True, timeout=None
                        )
                        time_took = time() - start_times[ret_uid]
                        report.write(
                            f'{ret_uid},{time_took},"{str(next_res_type)}",{1},{next_res != None}\n'
                        )
                        report.flush()
                        queue_size -= 1
                        if isinstance(next_res, str):
                            raise Exception(
                                "Synthesis procedure crashed, aborting\n" + next_res
                            )
                        elif next_res != None:
                            if exitFirstSuccess:
                                break
                        else:
                            print(
                                f"Failed to synthesize #{ret_uid} (structure: {next_res_type}, base depth: {baseDepth})"
                            )

        if exitFirstSuccess:
            if next_res == None:
                raise Exception("Synthesis failed")
            else:
                print(
                    "\n========================= SYNTHESIS COMPLETE =========================\n"
                )
                print("State Structure:", next_res_type)
                print("\nRuntime Logic:")
                print("\n\n".join([c.toRosette() for c in next_res]))  # type: ignore
                return (next_res_type, next_res)  # type: ignore
        else:
            print(f"See report file ({reportFile}) for results")
            return (next_res_type, [])
    finally:
        for p in process_tracker.all_processes:
            p.terminate()
        process_tracker.all_processes = []
