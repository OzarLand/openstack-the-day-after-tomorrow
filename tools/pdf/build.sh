#!/usr/bin/env bash
# Build the PDF edition of the book from the Markdown sources.
#
#   tools/pdf/build.sh [VERSION]
#
# VERSION is printed on the copyright page (for example "v1.1"). When it is
# omitted, the build is labelled as a development build with the commit hash.
# For compatibility with earlier versions of this script, a first argument
# "en" is ignored: "build.sh en v1.1" is "build.sh v1.1".
#
# Output: build/openstack-the-day-after-tomorrow.pdf (plus the LaTeX sources
# and logs, in build/, which is ignored by Git).
#
# Requirements: pandoc (>= 3.1), XeLaTeX (TeX Live with tcolorbox, titlesec,
# fancyhdr, microtype, enumitem, caption), the TeX Gyre and DejaVu fonts,
# rsvg-convert (librsvg) for the SVG figures.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "en" ]]; then shift; fi
VERSION="${1:-${BOOK_VERSION:-}}"
if [[ -z "$VERSION" ]]; then
  VERSION="development build ($(git rev-parse --short HEAD 2>/dev/null || echo unversioned))"
fi
DATE="$(date -u +%Y-%m-%d)"
REPO_URL="https://github.com/OzarLand/openstack-the-day-after-tomorrow"

BUILD=build
NAME=openstack-the-day-after-tomorrow
mkdir -p "$BUILD"

# ---- 0. Sources, metadata, title page, figures --------------------------------
METADATA=tools/pdf/metadata.yaml
FRONT_MATTER=chapters/00-front-matter.md
FIGURES=assets/figures
SOURCES=(
  chapters/00-how-to-read-this-book.md
  chapters/00-introduction.md
  chapters/0[1-9]-*.md
  chapters/1[0-9]-*.md
  chapters/20-*.md
  chapters/21-*.md
  appendices/appendix-[a-f]-*.md
  appendices/references-and-further-reading.md
)
TITLE="OpenStack,\\\\ the Day After Tomorrow"
SUBTITLE="Operating Mission-Critical OpenStack Platforms"
ABOUT="\\textbf{About this edition.} Version \\bookversion, generated on \\bookdate\\ from the
Markdown sources published at \\url{$REPO_URL}. Corrections and suggestions are
welcome through the issues of that repository."

# ---- 1. Ordered list of sources ---------------------------------------------
for f in "${SOURCES[@]}"; do [[ -f "$f" ]] || { echo "missing source: $f" >&2; exit 1; }; done
echo "Sources: ${#SOURCES[@]} files"

# ---- 2. Version stamp, title page and colophon (copyright page) --------------
cat > "$BUILD/version.tex" <<EOF
\\newcommand{\\bookversion}{$VERSION}
\\newcommand{\\bookdate}{$DATE}
\\newcommand{\\booktitle}{$TITLE}
\\newcommand{\\booksubtitle}{$SUBTITLE}
EOF

# The copyright page is the text of the front-matter file between the first
# horizontal rule (after the title block) and the navigation footer.
awk 'BEGIN{n=0} /^---$/{n++; next} n==1{print}' "$FRONT_MATTER" \
  | pandoc -f markdown -t latex -o "$BUILD/colophon-body.tex"
{
  cat "$BUILD/colophon-body.tex"
  printf '\n\\vspace{1em}\n%s\n' "$ABOUT"
} > "$BUILD/colophon.tex"

# ---- 3. Figures: SVG -> PDF (vector) ------------------------------------------
rm -rf "$BUILD/figures"; mkdir -p "$BUILD/figures"
for svg in "$FIGURES"/*.svg; do
  rsvg-convert -f pdf -o "$BUILD/figures/$(basename "${svg%.svg}").pdf" "$svg"
done
echo "Figures: $(ls "$BUILD"/figures/*.pdf | wc -l) converted from $FIGURES"

# ---- 4. Markdown -> LaTeX -----------------------------------------------------
pandoc "${SOURCES[@]}" \
  --from markdown+smart+autolink_bare_uris \
  --to latex \
  --template tools/pdf/template.tex \
  --metadata-file "$METADATA" \
  --include-in-header tools/pdf/header.tex \
  --lua-filter tools/pdf/filters/book.lua \
  --resource-path=.:chapters:appendices \
  --top-level-division=chapter \
  --pdf-engine=xelatex \
  --standalone \
  --output "$BUILD/$NAME.tex"

# ---- 5. LaTeX -> PDF (three passes for the table of contents and marks) -------
for pass in 1 2 3; do
  echo "XeLaTeX pass $pass"
  xelatex -interaction=nonstopmode -halt-on-error -file-line-error \
          -output-directory="$BUILD" "$BUILD/$NAME.tex" > "$BUILD/xelatex-pass$pass.out" 2>&1 \
    || { echo "XeLaTeX failed on pass $pass — last lines of the log:" >&2; tail -n 40 "$BUILD/$NAME.log" >&2; exit 1; }
done

test -s "$BUILD/$NAME.pdf" || { echo "PDF was not produced" >&2; exit 1; }
echo "Built $BUILD/$NAME.pdf ($(du -h "$BUILD/$NAME.pdf" | cut -f1), $(pdfinfo "$BUILD/$NAME.pdf" | awk '/^Pages/{print $2}') pages, $VERSION)"
