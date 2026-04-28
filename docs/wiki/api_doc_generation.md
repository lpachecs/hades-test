# API Doc Generation

Create the `.rst` structures for all modules

    poetry run sphinx-apidoc -o .\docs\source\ ldf

Build the HTML documentation from the `.rst` structures

    poetry run sphinx-build -b html .\docs\source\ .\docs\build\html\
   