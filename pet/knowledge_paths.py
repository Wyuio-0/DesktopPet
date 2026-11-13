"""Validate user supplied names before accessing knowledge-base files."""

import os
import re
import stat


class InvalidKnowledgePath(ValueError):
    """A name or filesystem link would escape the intended data directory."""


def validate_name(value):
    """Accept one portable filename component, including Windows restrictions."""
    if (not isinstance(value, str) or not value or value in (".", "..")
            or len(value) > 255 or value.endswith((".", " "))
            or re.search(r'[\x00-\x1f\x7f/\\:*?"<>|]', value)):
        raise InvalidKnowledgePath("名称无效：请勿使用路径、特殊字符、末尾空格或句点")
    stem = value.split(".", 1)[0].rstrip(" ").upper()
    if stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", stem):
        raise InvalidKnowledgePath("名称无效：不能使用 Windows 保留名称")
    return value


def course_name(value):
    """Normalize the UI's global-course markers; reject malformed names."""
    if value is None or value in ("", "__GLOBAL__", "__ALL__"):
        return ""
    name = validate_name(value)
    if name.casefold() == "_global":
        raise InvalidKnowledgePath("课程名 _global 为全局考纲保留名称")
    return name


def safe_child(root, *names):
    """Keep every child below root and reject symlinks and Windows junctions.

    The root is chosen by the application, while every child is untrusted.
    Rejecting reparse points also prevents aliases to other knowledge folders.
    """
    base = os.path.realpath(os.path.abspath(root))
    path = base
    for name in names:
        path = os.path.join(path, validate_name(name))
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            info = None
        if info is not None and (stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise InvalidKnowledgePath("知识库路径不能包含符号链接或目录联接")
        resolved = os.path.realpath(path)
        if os.path.commonpath((base, resolved)) != base or resolved == base:
            raise InvalidKnowledgePath("路径超出知识库目录")
    return path
