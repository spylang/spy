"""
SPy `aws` module.

Provides a loop-based API for AWS Lambda Function URLs.
This module only works when compiling to native; it cannot work in the
interpreter because it depends on the aws_lambda C SDK.
"""

from typing import TYPE_CHECKING

from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.w import W_Object, W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

AWS = ModuleRegistry("aws")


@AWS.builtin_func
def w_lambda_init(vm: "SPyVM") -> None:
    raise NotImplementedError("aws.lambda_init is only available in native builds")


@AWS.builtin_func
def w_lambda_next_body(vm: "SPyVM") -> W_Str:
    raise NotImplementedError("aws.lambda_next_body is only available in native builds")


@AWS.builtin_func
def w_response(vm: "SPyVM", w_status_code: W_I32, w_body: W_Str) -> None:
    raise NotImplementedError("aws.response is only available in native builds")
