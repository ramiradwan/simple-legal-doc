"""  
LaTeX rendering service.  
  
This module is responsible for transforming validated **Document Content**  
into a visually rendered PDF using LuaLaTeX.  
  
Design guarantees:  
- Deterministic template rendering (Jinja2 + StrictUndefined)  
- No shell escape or external execution  
- Compilation halted on LaTeX errors  
- No Document Content transformation occurs in this module  
  
RENDERING CONTRACT (ENFORCED):  
  
Callers MUST supply:  
- document_content:  
    Pure, validated Document Content supplied by the client.  
- bindings:  
    Engine-generated, non-authoritative presentation metadata  
    (e.g. declared content hash, generation mode).  
  
Rendering without bindings is intentionally unsupported.  
  
Trust boundary:  
- This module is presentation-only.  
- Canonicalization, hashing, archival normalization, and cryptographic  
  sealing occur strictly outside this module.  
"""  
  
import os  
import subprocess  
from pathlib import Path  
from typing import Any, Dict  
  
from jinja2 import Environment, FileSystemLoader, StrictUndefined  
  
  
TEMPLATE_ROOT = Path(  
    os.environ.get("TEMPLATE_DIR", "templates")  
).resolve()  
  
if not TEMPLATE_ROOT.is_dir():  
    raise RuntimeError(f"TEMPLATE_ROOT does not exist: {TEMPLATE_ROOT}")  
  
  
class LaTeXCompilationError(RuntimeError):  
    """Raised when LaTeX rendering or compilation fails."""  
  
  
def render_and_compile_pdf_to_path(  
    *,  
    template_path: str,  
    document_content: Dict[str, Any],  
    bindings: Dict[str, Any],  
    outdir: Path,  
) -> Path:  
    """  
    Render a LaTeX Jinja template and compile it to a PDF using LuaLaTeX.  
  
    The rendered PDF is written into ``outdir`` and the path to the PDF  
    artifact is returned.  
  
    IMPORTANT INVARIANTS:  
    - Document Content is passed through verbatim.  
    - Bindings are injected strictly for presentation.  
    - Bindings MUST NOT override Document Content fields.  
    - Canonicalization, hashing, normalization, and signing occur elsewhere.  
    - On failure, a LaTeXCompilationError is raised.  
    """  
  
    # ------------------------------------------------------------------  
    # Jinja template rendering (deterministic)  
    # ------------------------------------------------------------------  
    env = Environment(  
        loader=FileSystemLoader(TEMPLATE_ROOT),  
        block_start_string=r"\BLOCK{",  
        block_end_string="}",  
        variable_start_string=r"\VAR{",  
        variable_end_string="}",  
        comment_start_string=r"\#{",  
        comment_end_string="}",  
        undefined=StrictUndefined,  
        autoescape=False,  
    )  
  
    template = env.get_template(template_path)  
  
    # ------------------------------------------------------------------  
    # Render context construction (presentation-only)  
    # ------------------------------------------------------------------  
    render_context: Dict[str, Any] = dict(document_content)  
  
    for key, value in bindings.items():  
        if key in render_context:  
            raise LaTeXCompilationError(  
                f"Render context collision on key '{key}'. "  
                "Bindings must not override Document Content fields."  
            )  
        render_context[key] = value  
  
    rendered_tex = template.render(render_context)  
  
    tex_file = outdir / "document.tex"  
    tex_file.write_text(rendered_tex, encoding="utf-8")  
  
    # ------------------------------------------------------------------  
    # LuaLaTeX invocation (strict, sandboxed)  
    # ------------------------------------------------------------------  
    command = [  
        "lualatex",  
        "-interaction=nonstopmode",  
        "-halt-on-error",  
        "-no-shell-escape",  
        f"-output-directory={outdir}",  
        tex_file.name,  
    ]  
  
    env_vars = os.environ.copy()  
    existing_texinputs = env_vars.get("TEXINPUTS", "")  
    env_vars["TEXINPUTS"] = (  
        f"{TEMPLATE_ROOT.resolve()}{os.pathsep}{existing_texinputs}"  
    )  
  
    try:  
        process = subprocess.run(  
            command,  
            cwd=outdir,  
            stdout=subprocess.PIPE,  
            stderr=subprocess.PIPE,  
            timeout=60,  
            env=env_vars,  
            check=False,  
        )  
    except Exception as exc:  
        raise LaTeXCompilationError(  
            f"Failed to invoke LuaLaTeX: {exc}"  
        ) from exc  
  
    stdout = process.stdout.decode("utf-8", errors="ignore")  
    stderr = process.stderr.decode("utf-8", errors="ignore")  
  
    if process.returncode != 0:  
        raise LaTeXCompilationError(  
            "LuaLaTeX compilation failed.\n\n"  
            "STDOUT:\n"  
            f"{stdout}\n\n"  
            "STDERR:\n"  
            f"{stderr}"  
        )  
  
    pdf_file = outdir / "document.pdf"  
    if not pdf_file.exists():  
        raise LaTeXCompilationError(  
            "LuaLaTeX reported success, but no PDF output was produced."  
        )  
  
    return pdf_file  