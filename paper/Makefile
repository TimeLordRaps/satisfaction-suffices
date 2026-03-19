# Single source of truth: paper_01_submission.md
# Generate .tex and .pdf from the canonical markdown.
# Never edit .tex directly — it is a build artifact.

TEX  = paper_01_submission.tex
PDF  = paper_01_submission.pdf
SRC  = paper_01_submission.md

.PHONY: tex pdf clean

tex: $(TEX)
pdf: $(PDF)

$(TEX): $(SRC)
	pandoc $(SRC) -o $(TEX) --standalone \
		-V documentclass=article \
		-V fontsize=11pt \
		-V geometry=margin=1in \
		--natbib

$(PDF): $(TEX)
	pdflatex $(TEX)
	pdflatex $(TEX)

clean:
	$(RM) $(TEX) $(PDF) *.aux *.log *.out *.bbl *.blg
