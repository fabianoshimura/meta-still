"""Errors shared across modules."""

from __future__ import annotations


class MetaStillError(Exception):
    """Base for every error this project raises deliberately."""


class UnreadableVideo(MetaStillError):
    """A video could not be opened, or reports no usable duration."""
