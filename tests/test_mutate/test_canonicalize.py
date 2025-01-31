# -*- coding: utf-8 -*-

"""Tests for the canonicalization algorithm."""

import itertools as itt
import unittest
from typing import Sequence

from y0.dsl import A, B, C, D, Expression, One, P, Product, R, Sum, Variable, W, X, Y, Z
from y0.mutate import canonical_expr_equal, canonicalize


class TestCanonicalize(unittest.TestCase):
    """Tests for the canonicalization of a simplified algorithm."""

    def assert_canonicalize(
        self, expected: Expression, expression: Expression, ordering: Sequence[Variable]
    ) -> None:
        """Check that the expression is canonicalized properly given an ordering."""
        with self.subTest(
            expr=str(expression),
            ordering=", ".join(variable.name for variable in ordering),
        ):
            actual = canonicalize(expression, ordering)
            self.assertEqual(
                expected,
                actual,
                msg=f"\nExpected: {str(expression)}\nActual:   {str(actual)}",
            )

    def test_atomic(self):
        """Test canonicalization of atomic expressions."""
        for expected, expression, ordering in [
            (One(), One(), []),
            (P(A), P(A), [A]),
            (P(A | B), P(A | B), [A, B]),
            (P(A | (B, C)), P(A | (B, C)), [A, B, C]),
            (P(A | (B, C)), P(A | (C, B)), [A, B, C]),
        ]:
            self.assert_canonicalize(expected, expression, ordering)

        expected = P(A | (B, C, D))
        for b, c, d in itt.permutations((B, C, D)):
            expression = P(A | (b, c, d))
            self.assert_canonicalize(expected, expression, [A, B, C, D])

    def test_atomic_interventions(self):
        """Test canonicalization of atomic expressions containing interventions."""
        for expected, expression, ordering in [
            (P(A @ X), P(A @ X), [A, X]),
            (P(A @ [X, Y]), P(A @ [X, Y]), [A, X, Y]),
            (P(A @ [X, Y]), P(A @ [Y, X]), [A, X, Y]),
        ]:
            self.assert_canonicalize(expected, expression, ordering)

    def test_derived_atomic(self):
        """Test canonicalizing."""
        # Sum with no range
        self.assert_canonicalize(P(A), Sum(P(A)), [A])

        # Sum
        expected = expression = Sum(P(A), (R,))
        self.assert_canonicalize(expected, expression, [A, R])

        # Single Product
        self.assert_canonicalize(P(A), Product((P(A),)), [A])

        # Simple product (only atomic)
        expected = P(A) * P(B) * P(C)
        for a, b, c in itt.permutations((P(A), P(B), P(C))):
            expression = a * b * c
            self.assert_canonicalize(expected, expression, [A, B, C])

        # Nested product
        expected = P(A) * P(B) * P(C)
        for b, c in itt.permutations((P(B), P(C))):
            expression = Product((P(A), Product((b, c))))
            self.assert_canonicalize(expected, expression, [A, B, C])

            expression = Product((Product((P(A), b)), c))
            self.assert_canonicalize(expected, expression, [A, B, C])

        # Sum with simple product (only atomic)
        expected = Sum(P(A) * P(B) * P(C), (R,))
        for a, b, c in itt.permutations((P(A), P(B), P(C))):
            expression = Sum(a * b * c, (R,))
            self.assert_canonicalize(expected, expression, [A, B, C, R])

        # Fraction
        expected = expression = P(A) / P(B)
        self.assert_canonicalize(expected, expression, [A, B])

        # Fraction with simple products (only atomic)
        expected = (P(A) * P(B) * P(C)) / (P(X) * P(Y) * P(Z))
        for (a, b, c), (x, y, z) in itt.product(
            itt.permutations((P(A), P(B), P(C))),
            itt.permutations((P(X), P(Y), P(Z))),
        ):
            expression = (a * b * c) / (x * y * z)
            self.assert_canonicalize(expected, expression, [A, B, C, X, Y, Z])

    def test_mixed(self):
        """Test mixed expressions."""
        expected = expression = P(A) * Sum(P(B), (R,))
        self.assert_canonicalize(expected, expression, [A, B, R])

        expected = P(A) * Sum(P(B), (R,)) * Sum(P(C), (Y,))
        for a, b, c in itt.permutations((P(A), Sum(P(B), (R,)), Sum(P(C), (Y,)))):
            expression = a * b * c
            self.assert_canonicalize(expected, expression, [A, B, C, R, Y])

        expected = P(D) * Sum(P(A) * P(B) * P(C), (R,))
        for a, b, c in itt.permutations((P(A), P(B), P(C))):
            sum_expr = Sum(a * b * c, (R,))
            for left, right in itt.permutations((P(D), sum_expr)):
                self.assert_canonicalize(expected, left * right, [A, B, C, D, R])

        expected = P(X) * Sum(P(A) * P(B), (Y,)) * Sum(P(C) * P(D), (Z,))
        for (a, b), (c, d) in itt.product(
            itt.permutations((P(A), P(B))),
            itt.permutations((P(C), P(D))),
        ):
            sexpr = Sum(a * b, (Y,)) * Sum(c * d, (Z,))
            self.assert_canonicalize(expected, sexpr * P(X), [A, B, C, D, X, Y, Z])
            self.assert_canonicalize(expected, P(X) * sexpr, [A, B, C, D, X, Y, Z])

        expected = expression = Sum(P(A) / P(B), (R,))
        self.assert_canonicalize(expected, expression, [A, B, R])

        expected = expression = Sum(P(A) / Sum(P(B), (W,)), (X,)) * Sum(
            P(A) / Sum(P(B) / P(C), (Y,)), (Z,)
        )
        self.assert_canonicalize(expected, expression, [A, B, C, W, X, Y, Z])

    def test_non_markov(self):
        """Test non-markov distributions (e.g., with multiple children)."""
        for c1, c2 in itt.permutations([A, B]):
            # No conditions
            self.assert_canonicalize(P(A & B), P(c1 & c2), [A, B])
            # One condition, C
            self.assert_canonicalize(P(A & B | C), P(c1 & c2 | C), [A, B, C])
            # Two conditions, C and D
            for p1, p2 in itt.permutations([C, D]):
                expected = P(A & B | C | D)
                expression = P(c1 & c2 | (p1, p2))
                ordering = [A, B, C, D, R]
                self.assert_canonicalize(expected, expression, ordering)
                self.assert_canonicalize(Sum(expected, (R,)), Sum(expression, (R,)), ordering)

        for c1, c2, c3 in itt.permutations([A, B, C]):
            self.assert_canonicalize(P(A, B, C), P(c1, c2, c3), [A, B, C])
            for p1, p2, p3 in itt.permutations([X, Y, Z]):
                expected = P(A & B & C | (X, Y, Z))
                expression = P(c1 & c2 & c3 | (p1 & p2 & p3))
                ordering = [A, B, C, R, X, Y, Z]
                self.assert_canonicalize(expected, expression, ordering)
                self.assert_canonicalize(Sum(expected, (R,)), Sum(expression, (R,)), ordering)


class TestCanonicalizeEqual(unittest.TestCase):
    """Test the ability of the canonicalize function to check expressions being equal."""

    def test_expr_equal(self):
        """Check that canonicalized expressions are equal."""
        self.assertTrue(canonical_expr_equal(P(X), P(X)))
        self.assertFalse(canonical_expr_equal(P(X), P(Y)))
        self.assertFalse(canonical_expr_equal(P(X @ W), P(X)))
        self.assertFalse(canonical_expr_equal(P(X @ W), P(Y)))

        # Order changes
        self.assertTrue(canonical_expr_equal(P(X & Y), P(Y & X)))
