.DEFAULT_GOAL := main

LATEXMK := latexmk -xelatex -outdir=build

main: description designbook
	cp build/*.pdf ../

description: src/DESCRIPTION.tex
	@echo ">>> build $<" 
	@$(LATEXMK) $< 
	@echo ">>> built $<" 

designbook: src/DESIGNBOOK.tex
	@echo ">>> build $<" 
	@$(LATEXMK) $< 
	@echo ">>> built $<" 
	

DRAWIO_SRC := $(wildcard figs/src/*.drawio)
DRAWIO_PDF := $(patsubst figs/src/%.drawio, figs/%.pdf, $(DRAWIO_SRC))

drawio: $(DRAWIO_PDF)

$(DRAWIO_PDF): figs/%.pdf: figs/src/%.drawio
	drawio -x -f pdf -e --crop -o $@ $<

gitgraph:
	git-network-graph --svg-file figs/src/gitgraph.svg --color always --style ascii --reverse --format "<%an> %s"
	rsvg-convert -f pdf -o figs/gitgraph.pdf figs/src/gitgraph.svg