; xcf_export.scm - Headless GIMP: load the XCF named by GIMP_INPUT, flatten, save as the
; format implied by GIMP_OUTPUT's extension (png, jpeg or pdf - gimp-file-save dispatches on
; the file name).
;
; Paths travel through environment variables ON PURPOSE: a Windows path pasted into a
; script-fu string literal is mangled by backslash escaping, but (getenv ...) returns the
; value unparsed. Same contract as the FreeCAD scripts (FREECAD_INPUT/OUTPUT).
;
; Written for GIMP 3.x script-fu (the add-in's pinned major; measured against
; gimp-console-3.2). ASCII only: console output goes through the system code page and a
; non-ASCII character in a message once discarded a finished FreeCAD export.
(let* ((input  (getenv "GIMP_INPUT"))
       (output (getenv "GIMP_OUTPUT"))
       (image  (car (gimp-file-load RUN-NONINTERACTIVE input))))
  (gimp-image-flatten image)
  (gimp-file-save RUN-NONINTERACTIVE image output)
  (gimp-image-delete image))
(gimp-quit 0)
