from contextlib import contextmanager
from copy import copy
from functools import wraps
from typing import Optional

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

from core.globals import OTEL_ENDPOINT, OTEL_SERVICE_NAME, OTEL_NAMESPACE, OTEL_DEPLOYMENT_ENV
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


INHERITED_ATTRS_KEY = "olap.inherited_attrs"


class AttributeCascadingProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        inherited = context.get_value(INHERITED_ATTRS_KEY, parent_context)
        if inherited:
            for key, val in inherited.items(): # type: ignore
                span.set_attribute(key, val)

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=None):
        return True


resource = Resource.create(attributes={
    "service.name": OTEL_SERVICE_NAME,
    "service.namespace": OTEL_NAMESPACE,
    "deployment.environment": OTEL_DEPLOYMENT_ENV,
})

provider = TracerProvider(resource=resource)

provider.add_span_processor(AttributeCascadingProcessor())

exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT)
provider.add_span_processor(BatchSpanProcessor(exporter))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer(OTEL_SERVICE_NAME)


def shutdown():
    provider.shutdown()

@contextmanager
def _build_span(func, span_name, kind, extra_attrs):
    func_name = func.__name__
    namespace = func.__qualname__.rsplit('.', 1)[0] if '.' in func.__qualname__ else func.__module__
    name = span_name or f"{namespace}.{func_name}"

    existing_inherited = context.get_value(INHERITED_ATTRS_KEY) or {}
    token = context.attach(context.set_value(INHERITED_ATTRS_KEY, {
        **existing_inherited, # type: ignore
        "code.function": func_name,
        "code.namespace": namespace
    }))
    try:
        with tracer.start_as_current_span(name, kind=kind, attributes=extra_attrs) as span:
            yield span
    finally:
        context.detach(token)


def _handle_exception(span: trace.Span, e: Exception):
    span.record_exception(e)
    span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))


def traced_operation(
        span_name: Optional[str] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        **extra_attrs,
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with _build_span(func, span_name, kind, extra_attrs) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    _handle_exception(span, e)
                    raise

        return wrapper
    return decorator


def traced_operation_async(
        span_name: Optional[str] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        **extra_attrs,
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with _build_span(func, span_name, kind, extra_attrs) as span:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    _handle_exception(span, e)
                    raise

        return wrapper
    return decorator
