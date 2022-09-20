from dataclasses import dataclass
from metalift import ir
import typing
import itertools


class Lattice:
    def ir_type(self) -> ir.Type:
        raise NotImplementedError()

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        raise NotImplementedError()

    def bottom(self) -> ir.Expr:
        raise NotImplementedError()

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        raise NotImplementedError()

    def has_node_id(self) -> bool:
        raise NotImplementedError()


@dataclass(frozen=True)
class MaxInt(Lattice):
    int_type: ir.Type = ir.Int()

    def ir_type(self) -> ir.Type:
        return self.int_type

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        a_var = ir.Var("max_merge_a", self.int_type)
        b_var = ir.Var("max_merge_b", self.int_type)
        return ir.Let(
            a_var, a, ir.Let(b_var, b, ir.Ite(ir.Ge(a_var, b_var), a_var, b_var))
        )

    def bottom(self) -> ir.Expr:
        return ir.Lit(0, self.int_type)

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        return ir.Ge(v, self.bottom())

    def has_node_id(self) -> bool:
        return self.int_type == ir.NodeIDInt()


@dataclass(frozen=True)
class OrBool(Lattice):
    def ir_type(self) -> ir.Type:
        return ir.Bool()

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        return ir.Or(a, b)

    def bottom(self) -> ir.Expr:
        return ir.BoolLit(False)

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        return ir.BoolLit(True)

    def has_node_id(self) -> bool:
        return False


@dataclass(frozen=True)
class Set(Lattice):
    innerType: ir.Type

    def ir_type(self) -> ir.Type:
        return ir.SetT(self.innerType)

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        return ir.Call("set-union", ir.SetT(self.innerType), a, b)

    def bottom(self) -> ir.Expr:
        return ir.Call("set-create", ir.SetT(self.innerType))

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        return ir.BoolLit(True)

    def has_node_id(self) -> bool:
        return self.innerType == ir.NodeIDInt()


@dataclass(frozen=True)
class Map(Lattice):
    keyType: ir.Type
    valueType: Lattice

    def ir_type(self) -> ir.Type:
        return ir.MapT(self.keyType, self.valueType.ir_type())

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        v_a = ir.Var("map_merge_a", self.valueType.ir_type())
        v_b = ir.Var("map_merge_b", self.valueType.ir_type())

        return ir.Call(
            "map-union",
            ir.MapT(self.keyType, self.valueType.ir_type()),
            a,
            b,
            ir.Lambda(
                self.valueType.ir_type(), self.valueType.merge(v_a, v_b), v_a, v_b
            ),
        )

    def bottom(self) -> ir.Expr:
        return ir.Call("map-create", self.ir_type())

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        merge_a = ir.Var("merge_into", ir.Bool())
        merge_b = ir.Var("merge_v", self.valueType.ir_type())

        return ir.Call(
            "reduce_bool",
            ir.Bool(),
            ir.Call("map-values", ir.ListT(self.valueType.ir_type()), v),
            ir.Lambda(
                ir.Bool(),
                ir.And(merge_a, self.valueType.check_is_valid(merge_b)),
                merge_b,
                merge_a,
            ),
            ir.BoolLit(True),
        )

    def has_node_id(self) -> bool:
        return self.keyType == ir.NodeIDInt() or self.valueType.has_node_id()


@dataclass(frozen=True)
class LexicalProduct(Lattice):
    l1: Lattice
    l2: Lattice

    def ir_type(self) -> ir.Type:
        return ir.TupleT(self.l1.ir_type(), self.l2.ir_type())

    def merge(self, a: ir.Expr, b: ir.Expr) -> ir.Expr:
        mergeA = ir.Var("cascade_merge_a", a.type)
        mergeB = ir.Var("cascade_merge_b", b.type)

        keyA = ir.TupleGet(mergeA, ir.IntLit(0))
        keyB = ir.TupleGet(mergeB, ir.IntLit(0))
        valueA = ir.TupleGet(mergeA, ir.IntLit(1))
        valueB = ir.TupleGet(mergeB, ir.IntLit(1))

        keyMerged = self.l1.merge(keyA, keyB)
        valueMerged = self.l2.merge(valueA, valueB)

        return ir.Let(
            mergeA,
            a,
            ir.Let(
                mergeB,
                b,
                ir.Tuple(
                    keyMerged,
                    ir.Ite(
                        ir.Or(
                            ir.Eq(keyA, keyB),
                            ir.And(
                                ir.Not(ir.Eq(keyA, keyMerged)),
                                ir.Not(ir.Eq(keyB, keyMerged)),
                            ),
                        ),
                        valueMerged,
                        self.l2.merge(
                            ir.Ite(
                                ir.Eq(keyA, keyMerged),
                                valueA,
                                valueB,
                            ),
                            self.l2.bottom(),
                        ),
                    ),
                ),
            ),
        )

    def bottom(self) -> ir.Expr:
        return ir.Tuple(self.l1.bottom(), self.l2.bottom())

    def check_is_valid(self, v: ir.Expr) -> ir.Expr:
        return ir.And(
            self.l1.check_is_valid(ir.TupleGet(v, ir.IntLit(0))),
            self.l2.check_is_valid(ir.TupleGet(v, ir.IntLit(1))),
        )

    def has_node_id(self) -> bool:
        return self.l1.has_node_id() or self.l2.has_node_id()


def gen_types(depth: int) -> typing.Iterator[ir.Type]:
    if depth == 1:
        yield ir.Int()
        yield ir.ClockInt()
        yield ir.EnumInt()
        yield ir.OpaqueInt()
        yield ir.NodeIDInt()
        yield ir.Bool()
    else:
        for innerType in gen_types(depth - 1):
            yield innerType
            # TODO: anything else?


int_like = {ir.Int().name, ir.ClockInt().name, ir.EnumInt().name, ir.OpaqueInt().name}
comparable_int = {ir.Int().name, ir.ClockInt().name, ir.OpaqueInt().name}
set_supported_elem = {ir.Int().name, ir.OpaqueInt().name}
map_supported_elem = {ir.OpaqueInt().name, ir.NodeIDInt().name}


def gen_lattice_types(max_depth: int) -> typing.Iterator[Lattice]:
    if max_depth == 1:
        yield OrBool()

    for innerType in gen_types(max_depth):
        if innerType.name in comparable_int:
            yield MaxInt(innerType)

    if max_depth > 1:
        for innerLatticeType in gen_lattice_types(max_depth - 1):
            yield innerLatticeType

        for innerType in gen_types(max_depth - 1):
            if innerType.name in set_supported_elem:
                yield Set(innerType)

        for keyType in gen_types(max_depth - 1):
            if keyType.name in map_supported_elem:
                for valueType in gen_lattice_types(max_depth - 1):
                    yield Map(keyType, valueType)

        for innerTypePair in itertools.permutations(
            gen_lattice_types(max_depth - 1), 2
        ):
            yield LexicalProduct(*innerTypePair)


def gen_structures(max_depth: int) -> typing.Iterator[typing.Any]:
    cur_type_depth = 1
    seen = set()
    while cur_type_depth <= max_depth:
        print(f"Type depth: {cur_type_depth}")
        cur_tuple_size = 1
        while cur_tuple_size <= cur_type_depth:
            print(f"Tuple size: {cur_tuple_size}")
            for lattice_types in itertools.combinations_with_replacement(
                gen_lattice_types(cur_type_depth), cur_tuple_size
            ):
                if tuple(lattice_types) in seen:
                    continue
                else:
                    seen.add(tuple(lattice_types))
                    yield lattice_types
            cur_tuple_size += 1
        cur_type_depth += 1
