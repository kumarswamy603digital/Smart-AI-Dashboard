"""CSV upload, reset-to-sample and explicit cleaning callbacks."""
from __future__ import annotations

from dash import Input, Output, State, html, no_update, ctx

from src.data.loader import decode_upload, parse_csv_bytes, safe_filename
from src.data.validation import validate_upload
from src.services.dashboard_service import apply_cleaning, reset_to_sample, set_uploaded_frame

MAX_B64_CHARS = 4_194_304 * 4 // 3  # mirror of the byte cap in base64 units


def _ok(msg: str) -> html.Div:
    return html.Div(msg, className="notice-ok")


def _err(msg: str) -> html.Div:
    return html.Div(msg, className="notice-err")


def register(app) -> None:
    @app.callback(
        [Output("dataset-ver", "data"),
         Output("upload-status", "children"),
         Output("cleaning-status", "children")],
        [Input("csv-upload", "contents"),
         Input("csv-upload", "filename"),
         Input("reset-sample-btn", "n_clicks"),
         Input("clean-apply-btn", "n_clicks")],
        [State("session-token", "data"),
         State("dataset-ver", "data"),
         State("clean-options", "value")],
    )
    def dataset_events(contents, filename, reset_n, clean_n, token, ver, clean_opts):
        triggered = ctx.triggered_id
        if triggered in (None, "reset-sample-btn") and triggered != "reset-sample-btn":
            return no_update, no_update, no_update

        if triggered == "reset-sample-btn":
            reset_to_sample(token)
            return (ver or 0) + 1, _ok("Active dataset reset to the synthetic sample."), html.Div()

        if triggered == "clean-apply-btn":
            opts = clean_opts or []
            if not opts:
                return no_update, no_update, _err("Select at least one cleaning operation.")
            from src.services.dashboard_service import get_session
            is_sample = get_session(token)["is_sample"]
            session = apply_cleaning(token, "na" in opts, "dups" in opts, None)
            rep = session["cleaning_report"] or {}
            msg = (f"Cleaning applied to a copy: {rep.get('rows_before', 0):,} rows → "
                   f"{rep.get('rows_after', 0):,} rows (−{rep.get('rows_removed_missing', 0)} with missing values, "
                   f"−{rep.get('rows_removed_duplicates', 0)} duplicates). "
                   + ("Source sample regenerates from the seed." if is_sample else "Original upload preserved."))
            return (ver or 0) + 1, no_update, _ok(msg)

        # Upload path.
        if not contents or not filename:
            return no_update, no_update, no_update
        result = validate_upload(filename, contents)
        if not result.ok:
            return no_update, _err(" ".join(result.errors)), no_update
        try:
            raw = decode_upload(contents, filename)
            df = parse_csv_bytes(raw)
        except ValueError as exc:
            return no_update, _err(str(exc)), no_update
        name = safe_filename(filename)
        try:
            set_uploaded_frame(token, df, name)
        except ValueError as exc:
            return no_update, _err(str(exc)), no_update
        warn_block = ""
        vr = validate_warnings(df)
        if vr:
            warn_block = html.Div(vr, className="notice-warn")
        return ((ver or 0) + 1,
                html.Div([_ok(f"Loaded '{name}' — {len(df):,} rows × {df.shape[1]} columns. "
                              "Now active across all dashboard sections."), warn_block]),
                html.Div())


def validate_warnings(df) -> str:
    from src.data.validation import validate_frame

    return "; ".join(validate_frame(df).warnings)
