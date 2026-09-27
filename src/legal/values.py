"""Value grammar and exact mechanical format contracts."""

from __future__ import annotations

import calendar
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from .formats import fields, fail, integer, nonempty

DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


def decimal_value(value, path, positive=False):
    if not isinstance(value, str) or not DECIMAL.fullmatch(value):
        fail("INVALID_VALUE", path, "expected decimal string")
    number = Decimal(value)
    if positive and number <= 0:
        fail("INVALID_VALUE", path, "expected positive decimal")
    return number


def validate_units(config):
    fields(config, ["format_version", "version", "units"])
    if config["format_version"] != 1:
        fail("UNSUPPORTED_VERSION", "/format_version")
    nonempty(config["version"], "/version")
    if not isinstance(config["units"], list):
        fail("INVALID_ARGUMENT", "/units")
    by_code = {}
    for i, item in enumerate(config["units"]):
        path = f"/units/{i}"
        fields(item, ["code", "name", "dimension", "scale", "reference_unit", "aliases"], [], path)
        for field in ("code", "name", "dimension", "reference_unit"):
            nonempty(item[field], path + "/" + field)
        decimal_value(item["scale"], path + "/scale", positive=True)
        if item["code"] in by_code:
            fail("DUPLICATE_ID", path + "/code", "duplicate unit")
        if not isinstance(item["aliases"], list) or len(item["aliases"]) != len(set(item["aliases"])):
            fail("INVALID_ARGUMENT", path + "/aliases", "invalid aliases")
        for alias in item["aliases"]:
            nonempty(alias, path + "/aliases")
        by_code[item["code"]] = item
    for code, item in by_code.items():
        base = by_code.get(item["reference_unit"])
        if not base or base["dimension"] != item["dimension"] or base["reference_unit"] != base["code"] or base["scale"] != "1":
            fail("INVALID_ARGUMENT", "/units", f"invalid reference unit: {code}")
    return by_code


def _reference(value, path, resolver, kinds=None):
    if not isinstance(value, dict) or not ({"object_id", "record_id", "local_id"} & set(value)):
        fail("INVALID_VALUE", path, "expected reference")
    target = resolver(value, path)
    if kinds and target["kind"] not in kinds:
        fail("REFERENCE_TYPE_MISMATCH", path, "wrong reference target kind")
    return target


def validate_value(value, units, resolver, path="/value", depth=0):
    if value is None:
        return
    if depth > 100:
        fail("INVALID_VALUE", path, "value nesting too deep")
    if not isinstance(value, dict):
        fail("INVALID_VALUE", path, "expected value object")
    form = value.get("form")
    kind = value.get("kind")
    op = value.get("operator")
    if form is not None and not isinstance(form, str) or kind is not None and not isinstance(kind, str) or op is not None and not isinstance(op, str):
        fail("INVALID_VALUE", path, "form, kind and operator must be strings")
    child = lambda v, p: validate_value(v, units, resolver, p, depth + 1)
    if form == "quantity":
        fields(value, ["form", "amount", "unit"], [], path)
        if value["amount"] is not None:
            decimal_value(value["amount"], path + "/amount")
        if not isinstance(value["unit"], str) or value["unit"] not in units:
            fail("UNKNOWN_UNIT", path + "/unit", "unit not configured")
    elif form == "text":
        fields(value, ["form", "surface"], ["normalized"], path)
        nonempty(value["surface"], path + "/surface")
        if "normalized" in value:
            nonempty(value["normalized"], path + "/normalized")
    elif form == "reference":
        fields(value, ["form", "target"], [], path)
        _reference(value["target"], path + "/target", resolver)
    elif form == "time":
        if kind == "date":
            fields(value, ["form", "kind", "value", "precision"], ["boundary_text"], path)
            if value["precision"] not in {"year", "month", "day"}:
                fail("INVALID_VALUE", path + "/precision")
            if value["value"] is not None:
                pattern = {"year": r"[0-9]{4}", "month": r"[0-9]{4}-[0-9]{2}", "day": r"[0-9]{4}-[0-9]{2}-[0-9]{2}"}[value["precision"]]
                if not isinstance(value["value"], str) or not re.fullmatch(pattern, value["value"]):
                    fail("INVALID_VALUE", path + "/value", "invalid date form")
                parts = [int(p) for p in value["value"].split("-")]
                year = parts[0]
                month = parts[1] if len(parts) > 1 else 1
                day = parts[2] if len(parts) > 2 else 1
                if year < 1 or not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(year, month)[1]:
                    fail("INVALID_VALUE", path + "/value", "invalid calendar date")
        elif kind == "relative":
            fields(value, ["form", "kind", "event", "offset", "relation"], ["boundary_text"], path)
            _reference(value["event"], path + "/event", resolver, {"node:event"})
            if value["relation"] not in {"before", "after", "within_before", "within_after", "at"}:
                fail("INVALID_VALUE", path + "/relation")
            child(value["offset"], path + "/offset")
            _time_quantity(value["offset"], units, path + "/offset", value["relation"] != "at")
        elif kind == "duration":
            fields(value, ["form", "kind", "length"], ["boundary_text"], path)
            child(value["length"], path + "/length")
            _time_quantity(value["length"], units, path + "/length", True)
        elif kind == "interval":
            fields(value, ["form", "kind", "start", "end"], ["boundary_text"], path)
            for name in ("start", "end"):
                part = value[name]
                child(part, path + "/" + name)
                if part is not None and not ((part.get("form") == "time" and part.get("kind") in {"date", "relative"}) or (part.get("form") == "reference" and _reference(part["target"], path + "/" + name + "/target", resolver, {"node:event"}))):
                    fail("INVALID_VALUE", path + "/" + name, "invalid interval endpoint")
        else:
            fail("INVALID_VALUE", path + "/kind", "unknown time kind")
        if "boundary_text" in value:
            nonempty(value["boundary_text"], path + "/boundary_text")
    elif form == "condition":
        if op == "event":
            fields(value, ["form", "operator", "event"], [], path)
            _reference(value["event"], path + "/event", resolver, {"node:event"})
        elif op in {"all", "any"}:
            fields(value, ["form", "operator", "operands"], [], path)
            if not isinstance(value["operands"], list) or not value["operands"]:
                fail("INVALID_VALUE", path + "/operands")
            for i, part in enumerate(value["operands"]):
                child(part, f"{path}/operands/{i}")
                _expect(part, "condition", f"{path}/operands/{i}")
        elif op == "not":
            fields(value, ["form", "operator", "operand"], [], path)
            child(value["operand"], path + "/operand")
            _expect(value["operand"], "condition", path + "/operand")
        elif op == "compare":
            fields(value, ["form", "operator", "left", "comparison", "right"], [], path)
            _comparison(value["comparison"], path + "/comparison")
            for name in ("left", "right"):
                part = value[name]
                child(part, path + "/" + name)
                if part is not None and part.get("form") not in {"quantity", "time", "reference"}:
                    fail("INVALID_VALUE", path + "/" + name)
                if part is not None and part.get("form") == "reference":
                    target = _reference(part["target"], path + "/" + name + "/target", resolver,
                                        {"detail", "node:defined_value"})
                    target_value = target["data"].get("value")
                    if target_value is not None and target_value.get("form") not in {"quantity", "time"}:
                        fail("REFERENCE_TYPE_MISMATCH", path + "/" + name, "comparison target must be quantity or time")
        elif op == "count":
            fields(value, ["form", "operator", "condition", "comparison", "number", "mode"], ["period"], path)
            child(value["condition"], path + "/condition")
            _expect(value["condition"], "condition", path + "/condition")
            _comparison(value["comparison"], path + "/comparison")
            if value["number"] is not None:
                integer(value["number"], path + "/number", 0)
            if value["mode"] not in {"continuous", "total"}:
                fail("INVALID_VALUE", path + "/mode")
            if "period" in value:
                child(value["period"], path + "/period")
                if value["period"] is not None and value["period"].get("kind") not in {"duration", "interval"}:
                    fail("INVALID_VALUE", path + "/period")
        else:
            fail("INVALID_VALUE", path + "/operator", "unknown condition operator")
    elif form == "formula":
        fields(value, ["form", "operator", "operands"], [], path)
        if op not in {"add", "subtract", "multiply", "divide", "min", "max"} or not isinstance(value["operands"], list) or len(value["operands"]) < 2 or (op in {"subtract", "divide"} and len(value["operands"]) != 2):
            fail("INVALID_VALUE", path, "invalid formula operator or arity")
        dimensions = set()
        for i, part in enumerate(value["operands"]):
            child(part, f"{path}/operands/{i}")
            if part is not None and part.get("form") not in {"quantity", "reference", "formula"}:
                fail("INVALID_VALUE", f"{path}/operands/{i}")
            if part is not None and part.get("form") == "reference":
                _reference(part["target"], f"{path}/operands/{i}/target", resolver,
                           {"detail", "node:defined_value", "node:external_benchmark"})
            if part and part.get("form") == "quantity":
                dimensions.add(units[part["unit"]]["dimension"])
                if op == "divide" and i == 1 and part["amount"] is not None and Decimal(part["amount"]) == 0:
                    fail("INVALID_VALUE", f"{path}/operands/{i}", "division by zero")
        if op in {"add", "subtract", "min", "max"} and len(dimensions) > 1:
            fail("INVALID_VALUE", path, "incompatible dimensions")
    elif value.get("type") == "object":
        fields(value, ["type", "fields"], [], path)
        if not isinstance(value["fields"], dict):
            fail("INVALID_VALUE", path + "/fields")
        for name, part in value["fields"].items():
            child(part, path + "/fields/" + name)
    elif value.get("type") == "list":
        fields(value, ["type", "items"], [], path)
        if not isinstance(value["items"], list):
            fail("INVALID_VALUE", path + "/items")
        for i, part in enumerate(value["items"]):
            child(part, f"{path}/items/{i}")
    else:
        fail("INVALID_VALUE", path, "unknown value form")


def _expect(value, form, path):
    if value is not None and value.get("form") != form:
        fail("INVALID_VALUE", path, "wrong value form")


def _comparison(value, path):
    if value not in {"eq", "ne", "lt", "le", "gt", "ge"}:
        fail("INVALID_VALUE", path, "unknown comparison")


def _time_quantity(value, units, path, nonnegative):
    if value is not None:
        _expect(value, "quantity", path)
        if not units[value["unit"]]["dimension"].startswith("time:"):
            fail("INVALID_VALUE", path + "/unit", "expected time unit")
        if nonnegative and value["amount"] is not None and Decimal(value["amount"]) < 0:
            fail("INVALID_VALUE", path + "/amount", "negative time length")


def matches_schema(value, schema, units, resolver, path="/value"):
    if value is None:
        return
    if "one_of" in schema:
        successes = 0
        for branch in schema["one_of"]:
            try:
                matches_schema(value, branch, units, resolver, path)
                successes += 1
            except Exception as exc:
                from .formats import Invalid
                if not isinstance(exc, Invalid):
                    raise
        if successes != 1:
            fail("INVALID_VALUE", path, "value must match exactly one schema branch")
        return
    validate_value(value, units, resolver, path)
    if "form" in schema:
        if value.get("form") != schema["form"]:
            fail("INVALID_VALUE", path, "wrong form for slot")
        if schema["form"] == "quantity" and "allowed_units" in schema and value["unit"] not in schema["allowed_units"]:
            fail("INVALID_VALUE", path + "/unit", "unit not allowed")
        if schema["form"] == "text" and "enum" in schema and value.get("normalized", value["surface"]) not in schema["enum"]:
            fail("INVALID_VALUE", path, "text outside enumeration")
        if schema["form"] == "reference" and "target_kinds" in schema:
            _reference(value["target"], path + "/target", resolver, set(schema["target_kinds"]))
    elif schema.get("type") == "object":
        if value.get("type") != "object":
            fail("INVALID_VALUE", path, "expected object value")
        item_fields = value["fields"]
        if set(item_fields) - set(schema["fields"]) or set(schema.get("required_fields", [])) - set(item_fields):
            fail("INVALID_VALUE", path + "/fields", "object fields do not match schema")
        for name, part in item_fields.items():
            matches_schema(part, schema["fields"][name], units, resolver, path + "/fields/" + name)
    elif schema.get("type") == "list":
        if value.get("type") != "list":
            fail("INVALID_VALUE", path, "expected list value")
        for i, part in enumerate(value["items"]):
            matches_schema(part, schema["items"], units, resolver, f"{path}/items/{i}")


def check_contract(value, source, quote, path):
    contract = source.get("format_contract")
    surface = source.get("surface")
    params = source.get("format_parameters")
    if contract not in {"decimal.v1", "date.v1"}:
        fail("UNKNOWN_FORMAT_CONTRACT", path, "unknown format contract")
    if not isinstance(surface, str) or not surface or surface not in quote:
        fail("ROUNDTRIP_FAILED", path, "surface not found in quote")
    if contract == "decimal.v1":
        fields(params, ["decimal_places", "group_separator", "decimal_separator", "sign_style", "scale", "unit_surface", "unit_position", "prefix", "suffix", "number_unit_separator"], [], path)
        if not isinstance(value, dict) or value.get("form") != "quantity" or value.get("amount") is None:
            fail("ROUNDTRIP_FAILED", path, "decimal requires a quantity value")
        places = integer(params["decimal_places"], path, 0)
        group, sep = params["group_separator"], params["decimal_separator"]
        if group not in {"", ",", " ", "，"} or sep not in {".", ","} or (group and group == sep) or params["sign_style"] not in {"minus", "plus", "none"} or params["unit_position"] not in {"before", "after"}:
            fail("ROUNDTRIP_FAILED", path, "invalid decimal parameters")
        scale = decimal_value(params["scale"], path, positive=True)
        for name in ("unit_surface", "prefix", "suffix", "number_unit_separator"):
            if not isinstance(params[name], str) or re.search(r"[0-9]", params[name]):
                fail("ROUNDTRIP_FAILED", path, "invalid decimal literal")
        between = params["number_unit_separator"]
        unit = params["unit_surface"]
        start = params["prefix"] + (unit + between if params["unit_position"] == "before" else "")
        end = (between + unit if params["unit_position"] == "after" else "") + params["suffix"]
        if not surface.startswith(start) or not surface.endswith(end):
            fail("ROUNDTRIP_FAILED", path, "decimal literals differ")
        number = surface[len(start):len(surface) - len(end) if end else len(surface)]
        sign = number[:1] if number[:1] in {"+", "-"} else ""
        digits = number[1:] if sign else number
        if params["sign_style"] == "none" and sign or params["sign_style"] == "minus" and sign == "+" or params["sign_style"] == "plus" and sign == "":
            fail("ROUNDTRIP_FAILED", path, "decimal sign differs")
        components = digits.split(sep)
        if len(components) != (2 if places else 1) or places and len(components[1]) != places:
            fail("ROUNDTRIP_FAILED", path, "decimal places differ")
        integer_part = components[0]
        if group:
            if not re.fullmatch(r"[0-9]{1,3}(?:" + re.escape(group) + r"[0-9]{3})*", integer_part):
                fail("ROUNDTRIP_FAILED", path, "invalid grouping")
        elif not re.fullmatch(r"[0-9]+", integer_part):
            fail("ROUNDTRIP_FAILED", path, "invalid number")
        plain = sign + integer_part.replace(group, "") + ("." + components[1] if places else "")
        if Fraction(Decimal(plain)) * Fraction(scale) != Fraction(decimal_value(value["amount"], path)):
            fail("ROUNDTRIP_FAILED", path, "decimal amount differs")
        if Decimal(plain) >= 0 and sign == "-" and Decimal(plain) == 0:
            fail("ROUNDTRIP_FAILED", path, "negative zero does not round trip")
        if params["sign_style"] == "plus" and Decimal(plain) >= 0 and sign != "+":
            fail("ROUNDTRIP_FAILED", path, "positive value needs plus sign")
        integer_digits = str(int(integer_part.replace(group, "")))
        if group:
            pieces = []
            while len(integer_digits) > 3:
                pieces.append(integer_digits[-3:])
                integer_digits = integer_digits[:-3]
            integer_digits = group.join([integer_digits] + list(reversed(pieces)))
        expected_sign = "-" if Decimal(plain) < 0 else "+" if params["sign_style"] == "plus" else ""
        rendered = start + expected_sign + integer_digits + (sep + components[1] if places else "") + end
        if rendered != surface:
            fail("ROUNDTRIP_FAILED", path, "decimal surface does not round trip")
    else:
        fields(params, ["precision", "component_widths", "separators", "prefix", "suffix"], [], path)
        if not isinstance(value, dict) or value.get("form") != "time" or value.get("kind") != "date" or value.get("value") is None or params["precision"] != value["precision"]:
            fail("ROUNDTRIP_FAILED", path, "date target differs")
        count = {"year": 1, "month": 2, "day": 3}.get(value["precision"])
        widths, separators = params["component_widths"], params["separators"]
        if not isinstance(widths, list) or not isinstance(separators, list) or len(widths) != count or len(separators) != count - 1 or type(widths[0]) is not int or widths[0] != 4 or any(type(w) is not int or w not in (1, 2) for w in widths[1:]):
            fail("ROUNDTRIP_FAILED", path, "invalid date widths")
        if any(not isinstance(params[name], str) or re.search(r"[0-9]", params[name]) for name in ("prefix", "suffix")):
            fail("ROUNDTRIP_FAILED", path, "date literals cannot contain digits")
        for item in separators:
            if not isinstance(item, str) or re.search(r"[0-9]", item):
                fail("ROUNDTRIP_FAILED", path, "invalid date separator")
        parts = [int(x) for x in value["value"].split("-")]
        output = params["prefix"] + str(parts[0]).zfill(4)
        for i in range(1, count):
            output += separators[i - 1] + (str(parts[i]).zfill(2) if widths[i] == 2 else str(parts[i]))
        output += params["suffix"]
        if surface != output:
            fail("ROUNDTRIP_FAILED", path, "date surface differs")
