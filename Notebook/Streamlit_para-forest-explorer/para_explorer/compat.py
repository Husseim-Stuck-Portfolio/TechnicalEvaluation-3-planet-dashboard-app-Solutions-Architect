"""Small shims so the app runs on older and newer Streamlit versions.

Newer Streamlit (>=1.50ish) replaced ``use_container_width=True`` by ``width="stretch"`` and added
``st.iframe``; older releases only know ``use_container_width`` and ``components.html``.
Each helper inspects the installed signature once, so no version number is hard-coded.
"""
from __future__ import annotations

import inspect

import streamlit as st


def _stretch(fn) -> dict:
    """``width="stretch"`` where the parameter is the new string-typed one, else ``use_container_width``."""
    params = inspect.signature(fn).parameters
    w = params.get("width")
    if w is not None:
        ann = str(w.annotation).strip("'\"")
        if "stretch" in ann or ann == "Width" or "Literal" in ann or w.default in ("stretch", "content"):
            return {"width": "stretch"}
    return {"use_container_width": True} if "use_container_width" in params else {}


_KW = {name: _stretch(getattr(st, name)) for name in ("plotly_chart", "dataframe", "image")}


def plotly_chart(fig, **kw):
    return st.plotly_chart(fig, **{**_KW["plotly_chart"], **kw})


def dataframe(data, **kw):
    return st.dataframe(data, **{**_KW["dataframe"], **kw})


def image(img, **kw):
    return st.image(img, **{**_KW["image"], **kw})


def html_frame(html: str, height: int = 640):
    """Render a self-contained HTML document (our MapLibre globe) in an iframe."""
    if hasattr(st, "iframe"):
        return st.iframe(html, height=height)
    import streamlit.components.v1 as components
    return components.html(html, height=height)
