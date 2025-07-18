"""Test suite for `ethereum_test.code` module."""

from string import Template
from typing import Mapping

import pytest
from semver import Version

from ethereum_clis import TransitionTool
from ethereum_test_base_types import Account, Address, Hash, TestAddress, TestPrivateKey
from ethereum_test_fixtures import BlockchainFixture
from ethereum_test_forks import (
    Cancun,
    Fork,
    Homestead,
    Shanghai,
    get_deployed_forks,
)
from ethereum_test_specs import StateTest
from ethereum_test_types import Alloc, Environment, Transaction
from ethereum_test_vm import Opcodes as Op
from ethereum_test_vm import UndefinedOpcodes
from pytest_plugins.solc.solc import SOLC_EXPECTED_MIN_VERSION

from ..code import CalldataCase, Case, Conditional, Initcode, Switch


@pytest.fixture(params=get_deployed_forks())
def fork(request: pytest.FixtureRequest):
    """Return the target evm-version (fork) for solc compilation."""
    return request.param


@pytest.fixture()
def expected_bytes(request: pytest.FixtureRequest, solc_version: Version, fork: Fork):
    """Return the expected bytes for the test."""
    expected_bytes = request.param
    if isinstance(expected_bytes, Template):
        if solc_version < SOLC_EXPECTED_MIN_VERSION or fork <= Homestead:
            solc_padding = ""
        else:
            solc_padding = "00"
        return bytes.fromhex(expected_bytes.substitute(solc_padding=solc_padding))
    if isinstance(expected_bytes, bytes):
        if fork >= Shanghai:
            expected_bytes = b"\x5f" + expected_bytes[2:]
        if solc_version < SOLC_EXPECTED_MIN_VERSION or fork <= Homestead:
            return expected_bytes
        else:
            return expected_bytes + b"\x00"

    raise Exception("Unsupported expected_bytes type: {}".format(type(expected_bytes)))


@pytest.mark.parametrize(
    "initcode,bytecode",
    [
        pytest.param(
            Initcode(),
            bytes(
                [
                    0x61,
                    0x00,
                    0x00,
                    0x60,
                    0x00,
                    0x81,
                    0x60,
                    0x0B,
                    0x82,
                    0x39,
                    0xF3,
                ]
            ),
            id="empty-deployed-code",
        ),
        pytest.param(
            Initcode(initcode_prefix=Op.STOP),
            bytes(
                [
                    0x00,
                    0x61,
                    0x00,
                    0x00,
                    0x60,
                    0x00,
                    0x81,
                    0x60,
                    0x0C,
                    0x82,
                    0x39,
                    0xF3,
                ]
            ),
            id="empty-deployed-code-with-prefix",
        ),
        pytest.param(
            Initcode(initcode_length=20),
            bytes(
                [
                    0x61,
                    0x00,
                    0x00,
                    0x60,
                    0x00,
                    0x81,
                    0x60,
                    0x0B,
                    0x82,
                    0x39,
                    0xF3,
                ]
                + [0x00] * 9  # padding
            ),
            id="empty-deployed-code-with-padding",
        ),
        pytest.param(
            Initcode(deploy_code=Op.STOP, initcode_length=20),
            bytes(
                [
                    0x61,
                    0x00,
                    0x01,
                    0x60,
                    0x00,
                    0x81,
                    0x60,
                    0x0B,
                    0x82,
                    0x39,
                    0xF3,
                ]
                + [0x00]  # deployed code
                + [0x00] * 8  # padding
            ),
            id="single-byte-deployed-code-with-padding",
        ),
        pytest.param(
            Initcode(
                deploy_code=Op.STOP,
                initcode_prefix=Op.SSTORE(0, 1),
                initcode_length=20,
            ),
            bytes(
                [
                    0x60,
                    0x01,
                    0x60,
                    0x00,
                    0x55,
                    0x61,
                    0x00,
                    0x01,
                    0x60,
                    0x00,
                    0x81,
                    0x60,
                    0x10,
                    0x82,
                    0x39,
                    0xF3,
                ]
                + [0x00]  # deployed code
                + [0x00] * 3  # padding
            ),
            id="single-byte-deployed-code-with-padding-and-prefix",
        ),
    ],
)
def test_initcode(initcode: Initcode, bytecode: bytes):  # noqa: D103
    assert bytes(initcode) == bytecode


@pytest.mark.parametrize(
    "conditional_bytecode,expected",
    [
        (
            Conditional(
                condition=Op.CALLDATALOAD(0),
                if_true=Op.MSTORE(0, Op.SLOAD(0)) + Op.RETURN(0, 32),
                if_false=Op.SSTORE(0, 69),
            ),
            bytes.fromhex("600035600d5801576045600055600f5801565b60005460005260206000f35b"),
        ),
    ],
)
def test_opcodes_if(conditional_bytecode: bytes, expected: bytes):
    """Test that the if opcode macro is transformed into bytecode as expected."""
    assert bytes(conditional_bytecode) == expected


@pytest.mark.parametrize(
    "tx_data,switch_bytecode,expected_storage",
    [
        pytest.param(
            Hash(1),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                ],
                default_action=None,
            ),
            {0: 1},
            id="no-default-action-condition-met",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[
                    CalldataCase(value=1, action=Op.SSTORE(0, 1)),
                    CalldataCase(value=2, action=Op.SSTORE(0, 2)),
                ],
                default_action=None,
            ),
            {0: 1},
            id="no-default-action-condition-met-calldata",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                ],
                default_action=None,
            ),
            {0: 0},
            id="no-default-action-no-condition-met",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 3},
            id="no-cases",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1))],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 1},
            id="one-case-condition-met",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1))],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 3},
            id="one-case-condition-not-met",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                ],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 3},
            id="two-cases-no-condition-met",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                ],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 1},
            id="two-cases-first-condition-met",
        ),
        pytest.param(
            Hash(2),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                ],
                default_action=Op.SSTORE(0, 3),
            ),
            {0: 2},
            id="two-cases-second-condition-met",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 3)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 4), action=Op.SSTORE(0, 4)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 5), action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 1},
            id="five-cases-first-condition-met",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[
                    CalldataCase(value=1, action=Op.SSTORE(0, 1)),
                    CalldataCase(value=2, action=Op.SSTORE(0, 2)),
                    CalldataCase(value=3, action=Op.SSTORE(0, 3)),
                    CalldataCase(value=4, action=Op.SSTORE(0, 4)),
                    CalldataCase(value=5, action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 1},
            id="five-cases-first-condition-met-calldata",
        ),
        pytest.param(
            Hash(3),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 3)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 4), action=Op.SSTORE(0, 4)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 5), action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 3},
            id="five-cases-third-condition-met",
        ),
        pytest.param(
            Hash(3),
            Switch(
                cases=[
                    CalldataCase(value=1, action=Op.SSTORE(0, 1)),
                    CalldataCase(value=2, action=Op.SSTORE(0, 2)),
                    CalldataCase(value=3, action=Op.SSTORE(0, 3)),
                    CalldataCase(value=4, action=Op.SSTORE(0, 4)),
                    CalldataCase(value=5, action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 3},
            id="five-cases-third-condition-met-calldata",
        ),
        pytest.param(
            Hash(5),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 3)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 4), action=Op.SSTORE(0, 4)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 5), action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 5},
            id="five-cases-last-met",
        ),
        pytest.param(
            Hash(3),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 3)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 4)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 3},
            id="five-cases-multiple-conditions-met",  # first in list should be evaluated
        ),
        pytest.param(
            Hash(9),
            Switch(
                cases=[
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 2), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 3), action=Op.SSTORE(0, 3)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 4), action=Op.SSTORE(0, 4)),
                    Case(condition=Op.EQ(Op.CALLDATALOAD(0), 5), action=Op.SSTORE(0, 5)),
                ],
                default_action=Op.SSTORE(0, 6),
            ),
            {0: 6},
            id="five-cases-no-condition-met",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(1, 1), action=Op.SSTORE(0, 2)),
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                ],
                default_action=None,
            ),
            {0: 2},
            id="no-calldataload-condition-met",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                    Case(
                        condition=Op.EQ(1, 2),
                        action=Op.SSTORE(0, 1) + Op.SSTORE(1, 1) + Op.SSTORE(2, 1),
                    ),
                    Case(condition=Op.EQ(1, 1), action=Op.SSTORE(0, 2) + Op.SSTORE(1, 2)),
                    Case(condition=Op.EQ(1, 2), action=Op.SSTORE(0, 1)),
                ],
                default_action=None,
            ),
            {0: 2, 1: 2},
            id="no-calldataload-condition-met-different-length-actions",
        ),
        pytest.param(
            Hash(0),
            Switch(
                cases=[
                    Case(
                        condition=Op.EQ(1, 2),
                        action=Op.SSTORE(0, 1),
                    ),
                    Case(
                        condition=Op.EQ(Op.CALLDATALOAD(0), 1),
                        action=Op.SSTORE(0, 1),
                    ),
                    Case(
                        condition=Op.EQ(1, 2),
                        action=Op.SSTORE(0, 1) + Op.SSTORE(1, 1) + Op.SSTORE(2, 1),
                    ),
                    Case(
                        condition=Op.EQ(1, 1),
                        action=Op.SSTORE(0, 2) + Op.SSTORE(1, 2),
                    ),
                    Case(
                        condition=Op.EQ(Op.CALLDATALOAD(0), 1),
                        action=Op.SSTORE(0, 1),
                    ),
                ],
                default_action=None,
            ),
            {0: 2, 1: 2},
            id="different-length-conditions-condition-met-different-length-actions",
        ),
        pytest.param(
            Hash(0),
            Op.SSTORE(0x10, 1)
            + Switch(
                cases=[
                    Case(
                        condition=Op.EQ(1, 2),
                        action=Op.SSTORE(0, 1),
                    ),
                    Case(
                        condition=Op.EQ(Op.CALLDATALOAD(0), 1),
                        action=Op.SSTORE(0, 1),
                    ),
                    Case(
                        condition=Op.EQ(1, 2),
                        action=Op.SSTORE(0, 1) + Op.SSTORE(1, 1) + Op.SSTORE(2, 1),
                    ),
                    Case(
                        condition=Op.EQ(1, 1),
                        action=Op.SSTORE(0, 2) + Op.SSTORE(1, 2),
                    ),
                    Case(
                        condition=Op.EQ(Op.CALLDATALOAD(0), 1),
                        action=Op.SSTORE(0, 1),
                    ),
                ],
                default_action=None,
            )
            + Op.SSTORE(0x11, 1),
            {0: 2, 1: 2, 0x10: 1, 0x11: 1},
            id="nested-within-bytecode",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1))],
                default_action=Op.PUSH32(2**256 - 1) * 8,
            ),
            {0: 1},
            id="jumpi-larger-than-1-byte",
        ),
        pytest.param(
            Hash(1),
            Switch(
                cases=[Case(condition=Op.EQ(Op.CALLDATALOAD(0), 1), action=Op.SSTORE(0, 1))],
                default_action=Op.PUSH32(2**256 - 1) * 2048,
            ),
            {0: 1},
            id="jumpi-larger-than-4-bytes",
        ),
    ],
)
def test_switch(
    tx_data: bytes, switch_bytecode: bytes, expected_storage: Mapping, default_t8n: TransitionTool
):
    """Test that the switch opcode macro gets executed as using the t8n tool."""
    code_address = Address(0x1000)
    pre = Alloc(
        {
            code_address: Account(code=switch_bytecode),
            TestAddress: Account(balance=10_000_000),
        }
    )
    tx = Transaction(to=code_address, data=tx_data, gas_limit=1_000_000, secret_key=TestPrivateKey)
    post = {TestAddress: Account(nonce=1), code_address: Account(storage=expected_storage)}
    state_test = StateTest(
        env=Environment(),
        pre=pre,
        tx=tx,
        post=post,
    )
    state_test.generate(
        t8n=default_t8n,
        fork=Cancun,
        fixture_format=BlockchainFixture,
    )


def test_full_opcode_range():
    """
    Test that the full opcode range is covered by the opcode set defined by
    Opcodes and UndefineOpcodes.
    """
    assert len(set(Op) & set(UndefinedOpcodes)) == 0
    full_possible_opcode_set = set(Op) | set(UndefinedOpcodes)
    assert len(full_possible_opcode_set) == 257
    assert {op.hex() for op in full_possible_opcode_set} == {f"{i:02x}" for i in range(256)}
