# The print artifact. Two steps: the .typ is generated from the HTML, then compiled.
#
#   make typst   regenerate site/martelage.typ from the two HTML pages
#   make pdf     compile site/martelage-0.2.pdf from it
#   make check   verify every text node of the HTML appears in the PDF
#   make         = pdf
#
# SOURCE_DATE_EPOCH is pinned so the PDF's creation date is a constant: two builds of the
# same source are byte-identical. Without it Typst stamps the current second into the PDF
# and the hash changes on every build.

PYTHON ?= python3
TYPST ?= typst
SOURCE_DATE_EPOCH ?= 0
export SOURCE_DATE_EPOCH

.PHONY: all typst pdf check clean FORCE

all: pdf

# Always regenerate: the target is cheap and the output must follow the HTML.
typst:
	$(PYTHON) ../tools/html2typst.py


pdf:
	$(MAKE) typst
	$(TYPST) compile martelage.typ martelage-0.2.pdf


check: pdf
	$(PYTHON) ../tools/checktext.py

clean:
	rm -f martelage.typ martelage-0.2.pdf
