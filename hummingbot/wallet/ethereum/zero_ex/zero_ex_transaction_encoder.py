from typing import (
    List,
    Tuple
)
from decimal import Decimal
from mypy_extensions import TypedDict
from eth_abi import encode_single, encode_abi
from eth_utils import keccak, remove_0x_prefix, to_bytes, to_checksum_address

class SignedZeroExTransaction(TypedDict):
    verifyingContractAddress: str
    salt: str
    signerAddress: str
    data: str
    signature: str

class ZeroExTransaction(TypedDict):
    verifyingContractAddress: str
    salt: str
    signerAddress: str
    data: str

class EIP712TypedData(TypedDict):
    types: any
    domain: any
    message: any
    primaryType: str

def get_transaction_hash_hex(exchangeAddress: str, data: str, salt: Decimal, signerAddress: str) -> str:
    transaction: ZeroExTransaction = {
        'verifyingContractAddress': exchangeAddress,
        'salt': salt,
        'signerAddress': signerAddress,
        'data': data
    }

    typedData: EIP712TypedData = create_zero_ex_transaction_typed_data(transaction)
    transactionHashHex: str = generate_typed_data_hash(typedData)
        
    return transactionHashHex

def create_zero_ex_transaction_typed_data(zeroExTransaction: ZeroExTransaction) -> EIP712TypedData:
    typedData: EIP712TypedData = {
        'types': {
            'EIP712Domain': [
                { 'name': 'name', 'type': 'string' },
                { 'name': 'version', 'type': 'string' },
                { 'name': 'verifyingContract', 'type': 'address' }
            ],
            'ZeroExTransaction': [
                { 'name': 'salt', 'type': 'uint256' },
                { 'name': 'signerAddress', 'type': 'address' },
                { 'name': 'data', 'type': 'bytes' }
            ]
        },
        'domain': {
            'name': '0x Protocol',
            'version': '2',
            'verifyingContract': zeroExTransaction['verifyingContractAddress'],
        },
        'message': zeroExTransaction,
        'primaryType': "ZeroExTransaction"
    }

    return typedData

def generate_typed_data_hash(typedData: EIP712TypedData) -> str:
    return '0x' + keccak(
        b"\x19\x01" +
        _struct_hash('EIP712Domain', typedData['domain'], typedData['types']) +
        _struct_hash(typedData['primaryType'], typedData['message'], typedData['types'])
    ).hex()


def _find_dependencies(primaryType: str, types, found = None) -> List[str]:
    if found is None: 
        found = []

    if (primaryType in found) or (primaryType not in types):
        return found

    found.append(primaryType)

    for field in types[primaryType]:
        for dep in _find_dependencies(field['type'], types, found):
            if dep not in found:
                found.append(dep)        
    
    return found
    
def _encode_type(primaryType: str, types) -> str:
    deps = _find_dependencies(primaryType, types)
    deps = [d for d in deps if d != primaryType]
    deps.sort()
    deps = [primaryType] + deps
    result = ''
    seperator = ','

    for dep in deps:
        result += dep + '(' + seperator.join(list(map(lambda item: item['type'] + ' ' + item['name'], types[dep]))) + ')'

    return result

def _encode_data(primaryType: str, data: any, types) -> str:
    encodedTypes = ['bytes32']
    encodedValues = [_type_hash(primaryType, types)]

    for field in types[primaryType]:
        value = data[field['name']]

        if field['type'] == 'string':
            hashValue = keccak(text=value)
            encodedTypes.append('bytes32')
            encodedValues.append(hashValue)

        elif field['type'] == 'bytes':
            hashValue = keccak(hexstr=value)
            encodedTypes.append('bytes32')
            encodedValues.append(hashValue)

        elif field['type'] in types:
            encodedTypes.append('bytes32')
            hashValue = keccak(_encode_data(field['type'], value, types).encode())
            encodedValues.append(hashValue)

        elif field['type'] == 'uint256':
            encodedTypes.append('uint256')
            encodedValues.append(int(value))

        else:
            encodedTypes.append(field['type'])
            normalizedValue = _normalize_value(field['type'], value)
            encodedValues.append(normalizedValue)

    return encode_abi(encodedTypes, encodedValues)
    
def _normalize_value(type: str, value: any) -> any:
    if type == 'uint256':
        return str(value)
    else:
        return value
    
def _type_hash(primaryType: str, types) -> str:
    return keccak(_encode_type(primaryType, types).encode())


def _struct_hash(primaryType: str, data: any, types) -> str:
    return keccak(_encode_data(primaryType, data, types))