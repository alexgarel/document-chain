#!/usr/bin/python

### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 only
###
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
###
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
### Copyright 2007-2010 Dag Wieers <dag@wieers.com>

import getopt, sys, os, glob, time, socket, subprocess

__version__ = "$Revision$"
# $Source$

VERSION = '0.5'

doctypes = ('document', 'graphics', 'presentation', 'spreadsheet')

global convertor, office, ooproc, product
ooproc = None
exitcode = 0

class Office:
    def __init__(self, basepath, urepath, unopath, pyuno, binary, python, pythonhome):
        self.basepath = basepath
        self.urepath = urepath
        self.unopath = unopath
        self.pyuno = pyuno
        self.binary = binary
        self.python = python
        self.pythonhome = pythonhome

    def __str__(self):
        return self.basepath

    def __repr__(self):
        return self.basepath

### The first thing we ought to do is find a suitable Office installation
### with a compatible pyuno library that we can import.
###
### See: http://user.services.openoffice.org/en/forum/viewtopic.php?f=45&t=36370&p=166783

def find_offices():
    ret = []
    extrapaths = []

    ### Try using UNO_PATH first (in many incarnations, we'll see what sticks)
    if 'UNO_PATH' in os.environ:
        extrapaths += [ os.environ['UNO_PATH'],
                        os.path.dirname(os.environ['UNO_PATH']),
                        os.path.dirname(os.path.dirname(os.environ['UNO_PATH'])) ]
    else:

        if os.name in ( 'nt', 'os2' ):
            if 'PROGRAMFILES' in os.environ.keys():
                extrapaths += glob.glob(os.environ['PROGRAMFILES']+'\\LibreOffice*') + \
                              glob.glob(os.environ['PROGRAMFILES']+'\\OpenOffice.org*')

            if 'PROGRAMFILES(X86)' in os.environ.keys():
                extrapaths += glob.glob(os.environ['PROGRAMFILES(X86)']+'\\LibreOffice*') + \
                              glob.glob(os.environ['PROGRAMFILES(X86)']+'\\OpenOffice.org*')

        elif os.name in ( 'mac', ) or sys.platform in ( 'darwin', ):
            extrapaths += [ '/Applications/LibreOffice.app/Contents',
                            '/Applications/NeoOffice.app/Contents',
                            '/Applications/OpenOffice.org.app/Contents' ]

        else:
            extrapaths += glob.glob('/usr/lib*/libreoffice*') + \
                          glob.glob('/usr/lib*/openoffice*') + \
                          glob.glob('/usr/lib*/ooo*') + \
                          glob.glob('/opt/libreoffice*') + \
                          glob.glob('/opt/openoffice*') + \
                          glob.glob('/opt/ooo*') + \
                          glob.glob('/usr/local/libreoffice*') + \
                          glob.glob('/usr/local/openoffice*') + \
                          glob.glob('/usr/local/ooo*') + \
                          glob.glob('/usr/local/lib/libreoffice*')

    ### Find a working set of pyuno module
    for basepath in extrapaths:
        if os.name in ( 'nt', 'os2' ):
            officelibrary = 'pyuno.pyd'
            officebinary = 'soffice.exe'
            pythonbinary = 'python.exe'
        else:
            officelibrary = 'pyuno.so'
            officebinary = 'soffice.bin'
            pythonbinary = 'python.bin'

        ### Older LibreOffice/OpenOffice and Windows use basis-link/ or basis/
        basis = 'error'
        for sub in ('basis-link', 'basis', ''):
            if os.path.isfile(os.path.join(basepath, sub, 'program', officelibrary)):
                basis = sub
                break

        ### Windows does not provide or need a URE/lib directory ?
        ure = 'error'
        for sub in ('ure-link', 'ure', 'URE', ''):
            if os.path.isfile(os.path.join(basepath, basis, sub, 'lib', 'unorc')):
                ure = sub
                break

        ### MacOSX have soffice binaries installed in MacOS subdirectory, not program
        program = 'error'
        for sub in ('program', 'MacOS'):
            if os.path.isfile(os.path.join(basepath, basis, sub, officebinary)):
                program = os.path.join(basis, sub)
                break
            elif os.path.isfile(os.path.join(basepath, sub, officebinary)):
                program = sub
                break

        if not os.path.isfile(os.path.join(basepath, program, officebinary)):
            continue

#        if not glob.glob(os.path.join(basepath, basis, program, 'python-core-*')):
#            continue

        if os.path.isfile(os.path.join(basepath, basis, program, pythonbinary)):
            ret.append(Office(basepath,
                              os.path.join(basepath, basis, ure),
                              os.path.join(basepath, basis, program),
                              os.path.join(basepath, basis, program, officelibrary),
                              os.path.join(basepath, program, officebinary),
                              os.path.join(basepath, basis, program, pythonbinary),
                              glob.glob(os.path.join(basepath, basis, program, 'python-core-*'))[0]))
        else:
            ret.append(Office(basepath,
                              os.path.join(basepath, basis, ure),
                              os.path.join(basepath, basis, program),
                              os.path.join(basepath, basis, program, officelibrary),
                              os.path.join(basepath, program, officebinary),
                              sys.executable,
                              None))

    return ret

def office_environ(office):
    ### Set PATH so that crash_report is found
    os.environ['PATH'] = os.path.join(office.basepath, 'program') + os.pathsep + os.environ['PATH']

    ### Set UNO_PATH so that "officehelper.bootstrap()" can find soffice executable:
    os.environ['UNO_PATH'] = office.unopath

    ### Set URE_BOOTSTRAP so that "uno.getComponentContext()" bootstraps a complete
    ### UNO environment
    if os.name in ( 'nt', 'os2' ):
        os.environ['URE_BOOTSTRAP'] = 'vnd.sun.star.pathname:' + os.path.join(office.basepath, 'program', 'fundamental.ini')
    else:
        os.environ['URE_BOOTSTRAP'] = 'vnd.sun.star.pathname:' + os.path.join(office.basepath, 'program', 'fundamentalrc')

        ### Set LD_LIBRARY_PATH so that "import pyuno" finds libpyuno.so:
        if 'LD_LIBRARY_PATH' in os.environ:
            os.environ['LD_LIBRARY_PATH'] = office.unopath + os.pathsep + \
                                            os.path.join(office.urepath, 'lib') + os.pathsep + \
                                            os.environ['LD_LIBRARY_PATH']
        else:
            os.environ['LD_LIBRARY_PATH'] = office.unopath + os.pathsep + \
                                            os.path.join(office.urepath, 'lib')

    if office.pythonhome:
        for libpath in ( os.path.join(office.pythonhome, 'lib'),
                         os.path.join(office.pythonhome, 'lib', 'lib-dynload'),
                         os.path.join(office.pythonhome, 'lib', 'lib-tk'),
                         os.path.join(office.pythonhome, 'lib', 'site-packages'),
                         office.unopath):
            sys.path.insert(0, libpath)
    else:
        ### Still needed for system python using LibreOffice UNO bindings
        ### Although we prefer to use a system UNO binding in this case
        sys.path.append(office.unopath)

def debug_office():
    print 'sysname=%s' % os.name
    print 'platform=%s' % sys.platform
    print 'python=%s' % sys.executable
    print 'python-version=%s' % sys.version
    if 'URE_BOOTSTRAP' in os.environ:
        print 'URE_BOOTSTRAP=%s' % os.environ['URE_BOOTSTRAP']
    if 'UNO_PATH' in os.environ:
        print 'UNO_PATH=%s' % os.environ['UNO_PATH']
    if 'UNO_TYPES' in os.environ:
        print 'UNO_TYPES=%s' % os.environ['UNO_TYPES']
    print 'PATH=%s' % os.environ['PATH']
    if 'PYTHONHOME' in os.environ:
        print 'PYTHONHOME=%s' % os.environ['PYTHONHOME']
    if 'PYTHONPATH' in os.environ:
        print 'PYTHONPATH=%s' % os.environ['PYTHONPATH']
    if 'LD_LIBRARY_PATH' in os.environ:
        print 'LD_LIBRARY_PATH=%s' % os.environ['LD_LIBRARY_PATH']

def python_switch(office):
#   print >>sys.stderr, "WARNING: It is recommended to use python %s to run unoconv" % pybin
    if office.pythonhome:
        os.environ['PYTHONHOME'] = office.pythonhome
        os.environ['PYTHONPATH'] = os.path.join(office.pythonhome, 'lib') + os.pathsep + \
                                   os.path.join(office.pythonhome, 'lib', 'lib-dynload') + os.pathsep + \
                                   os.path.join(office.pythonhome, 'lib', 'lib-tk') + os.pathsep + \
                                   os.path.join(office.pythonhome, 'lib', 'site-packages') + os.pathsep + \
                                   office.unopath

    os.environ['UNO_PATH'] = office.unopath

#    print >>sys.stderr, "Switching from python %s to %s" % (sys.executable, office.python)
    if os.name in ('nt', 'os2'):
        ### os.execv is broken on Windows and can't properly parse command line
        ### arguments and executable name if they contain whitespaces. subprocess
        ### fixes that behavior.
        ret = subprocess.call([office.python] + sys.argv[0:])
        sys.exit(ret)
    else:

        ### Set LD_LIBRARY_PATH so that "import pyuno" finds libpyuno.so:
        if 'LD_LIBRARY_PATH' in os.environ:
            os.environ['LD_LIBRARY_PATH'] = office.unopath + os.pathsep + \
                                            os.path.join(office.urepath, 'lib') + os.pathsep + \
                                            os.environ['LD_LIBRARY_PATH']
        else:
            os.environ['LD_LIBRARY_PATH'] = office.unopath + os.pathsep + \
                                            os.path.join(office.urepath, 'lib')

        try:
            os.execvpe(office.python, [office.python, ] + sys.argv[0:], os.environ)
        except OSError:
            ### Mac OS X versions prior to 10.6 do not support execv in
            ### a process that contains multiple threads.  Instead of
            ### re-executing in the current process, start a new one
            ### and cause the current process to exit.  This isn't
            ### ideal since the new process is detached from the parent
            ### terminal and thus cannot easily be killed with ctrl-C,
            ### but it's better than not being able to autoreload at
            ### all.
            ### Unfortunately the errno returned in this case does not
            ### appear to be consistent, so we can't easily check for
            ### this error specifically.
            ret = os.spawnvpe(os.P_WAIT, office.python, [office.python, ] + sys.argv[0:], os.environ)
            sys.exit(ret)

class Fmt:
    def __init__(self, doctype, name, extension, summary, filter):
        self.doctype = doctype
        self.name = name
        self.extension = extension
        self.summary = summary
        self.filter = filter

    def __str__(self):
        return "%s [.%s]" % (self.summary, self.extension)

    def __repr__(self):
        return "%s/%s" % (self.name, self.doctype)

class FmtList:
    def __init__(self):
        self.list = []

    def add(self, doctype, name, extension, summary, filter):
        self.list.append(Fmt(doctype, name, extension, summary, filter))

    def byname(self, name):
        ret = []
        for fmt in self.list:
            if fmt.name == name:
                ret.append(fmt)
        return ret

    def byextension(self, extension):
        ret = []
        for fmt in self.list:
            if os.extsep + fmt.extension == extension:
                ret.append(fmt)
        return ret

    def bydoctype(self, doctype, name):
        ret = []
        for fmt in self.list:
            if fmt.name == name and fmt.doctype == doctype:
                ret.append(fmt)
        return ret

    def display(self, doctype):
        print >>sys.stderr, "The following list of %s formats are currently available:\n" % doctype
        for fmt in self.list:
            if fmt.doctype == doctype:
                print >>sys.stderr, "  %-8s - %s" % (fmt.name, fmt)
        print >>sys.stderr

fmts = FmtList()

### TextDocument
fmts.add('document', 'bib', 'bib', 'BibTeX', 'BibTeX_Writer') ### 22
fmts.add('document', 'doc', 'doc', 'Microsoft Word 97/2000/XP', 'MS Word 97') ### 29
fmts.add('document', 'doc6', 'doc', 'Microsoft Word 6.0', 'MS WinWord 6.0') ### 24
fmts.add('document', 'doc95', 'doc', 'Microsoft Word 95', 'MS Word 95') ### 28
fmts.add('document', 'docbook', 'xml', 'DocBook', 'DocBook File') ### 39
fmts.add('document', 'docx', 'docx', 'Microsoft Office Open XML', 'Office Open XML Text')
fmts.add('document', 'docx7', 'docx', 'Microsoft Office Open XML', 'MS Word 2007 XML')
fmts.add('document', 'fodt', 'fodt', 'OpenDocument Text (Flat XML)', 'OpenDocument Text Flat XML')
fmts.add('document', 'html', 'html', 'HTML Document (OpenOffice.org Writer)', 'HTML (StarWriter)') ### 3
fmts.add('document', 'latex', 'ltx', 'LaTeX 2e', 'LaTeX_Writer') ### 31
fmts.add('document', 'mediawiki', 'txt', 'MediaWiki', 'MediaWiki')
fmts.add('document', 'odt', 'odt', 'ODF Text Document', 'writer8') ### 10
fmts.add('document', 'ooxml', 'xml', 'Microsoft Office Open XML', 'MS Word 2003 XML') ### 11
fmts.add('document', 'ott', 'ott', 'Open Document Text', 'writer8_template') ### 21
fmts.add('document', 'pdb', 'pdb', 'AportisDoc (Palm)', 'AportisDoc Palm DB')
fmts.add('document', 'pdf', 'pdf', 'Portable Document Format', 'writer_pdf_Export') ### 18
fmts.add('document', 'psw', 'psw', 'Pocket Word', 'PocketWord File')
fmts.add('document', 'rtf', 'rtf', 'Rich Text Format', 'Rich Text Format') ### 16
fmts.add('document', 'sdw', 'sdw', 'StarWriter 5.0', 'StarWriter 5.0') ### 23
fmts.add('document', 'sdw4', 'sdw', 'StarWriter 4.0', 'StarWriter 4.0') ### 2
fmts.add('document', 'sdw3', 'sdw', 'StarWriter 3.0', 'StarWriter 3.0') ### 20
fmts.add('document', 'stw', 'stw', 'Open Office.org 1.0 Text Document Template', 'writer_StarOffice_XML_Writer_Template') ### 9
fmts.add('document', 'sxw', 'sxw', 'Open Office.org 1.0 Text Document', 'StarOffice XML (Writer)') ### 1
fmts.add('document', 'text', 'txt', 'Text Encoded', 'Text (Encoded)') ### 26
fmts.add('document', 'txt', 'txt', 'Text', 'Text') ### 34
fmts.add('document', 'uot', 'uot', 'Unified Office Format text','UOF text') ### 27
fmts.add('document', 'vor', 'vor', 'StarWriter 5.0 Template', 'StarWriter 5.0 Vorlage/Template') ### 6
fmts.add('document', 'vor4', 'vor', 'StarWriter 4.0 Template', 'StarWriter 4.0 Vorlage/Template') ### 5
fmts.add('document', 'vor3', 'vor', 'StarWriter 3.0 Template', 'StarWriter 3.0 Vorlage/Template') ### 4
fmts.add('document', 'xhtml', 'html', 'XHTML Document', 'XHTML Writer File') ### 33

### WebDocument
fmts.add('web', 'etext', 'txt', 'Text Encoded (OpenOffice.org Writer/Web)', 'Text (encoded) (StarWriter/Web)') ### 14
fmts.add('web', 'html10', 'html', 'OpenOffice.org 1.0 HTML Template', 'writer_web_StarOffice_XML_Writer_Web_Template') ### 11
fmts.add('web', 'html', 'html', 'HTML Document', 'HTML') ### 2
fmts.add('web', 'html', 'html', 'HTML Document Template', 'writerweb8_writer_template') ### 13
fmts.add('web', 'mediawiki', 'txt', 'MediaWiki', 'MediaWiki_Web') ### 9
fmts.add('web', 'pdf', 'pdf', 'PDF - Portable Document Format', 'writer_web_pdf_Export') ### 10
fmts.add('web', 'sdw3', 'sdw', 'StarWriter 3.0 (OpenOffice.org Writer/Web)', 'StarWriter 3.0 (StarWriter/Web)') ### 3
fmts.add('web', 'sdw4', 'sdw', 'StarWriter 4.0 (OpenOffice.org Writer/Web)', 'StarWriter 4.0 (StarWriter/Web)') ### 4
fmts.add('web', 'sdw', 'sdw', 'StarWriter 5.0 (OpenOffice.org Writer/Web)', 'StarWriter 5.0 (StarWriter/Web)') ### 5
fmts.add('web', 'txt', 'txt', 'OpenOffice.org Text (OpenOffice.org Writer/Web)', 'writerweb8_writer') ### 12
fmts.add('web', 'text10', 'txt', 'OpenOffice.org 1.0 Text Document (OpenOffice.org Writer/Web)', 'writer_web_StarOffice_XML_Writer') ### 15
fmts.add('web', 'text', 'txt', 'Text (OpenOffice.org Writer/Web)', 'Text (StarWriter/Web)') ### 8
fmts.add('web', 'vor4', 'vor', 'StarWriter/Web 4.0 Template', 'StarWriter/Web 4.0 Vorlage/Template') ### 6
fmts.add('web', 'vor', 'vor', 'StarWriter/Web 5.0 Template', 'StarWriter/Web 5.0 Vorlage/Template') ### 7

### Spreadsheet
fmts.add('spreadsheet', 'csv', 'csv', 'Text CSV', 'Text - txt - csv (StarCalc)') ### 16
fmts.add('spreadsheet', 'dbf', 'dbf', 'dBASE', 'dBase') ### 22
fmts.add('spreadsheet', 'dif', 'dif', 'Data Interchange Format', 'DIF') ### 5
fmts.add('spreadsheet', 'fods', 'fods', 'OpenDocument Spreadsheet (Flat XML)', 'OpenDocument Spreadsheet Flat XML')
fmts.add('spreadsheet', 'html', 'html', 'HTML Document (OpenOffice.org Calc)', 'HTML (StarCalc)') ### 7
fmts.add('spreadsheet', 'ods', 'ods', 'ODF Spreadsheet', 'calc8') ### 15
fmts.add('spreadsheet', 'ooxml', 'xml', 'Microsoft Excel 2003 XML', 'MS Excel 2003 XML') ### 23
fmts.add('spreadsheet', 'ots', 'ots', 'ODF Spreadsheet Template', 'calc8_template') ### 14
fmts.add('spreadsheet', 'pdf', 'pdf', 'Portable Document Format', 'calc_pdf_Export') ### 34
fmts.add('spreadsheet', 'pxl', 'pxl', 'Pocket Excel', 'Pocket Excel')
fmts.add('spreadsheet', 'sdc', 'sdc', 'StarCalc 5.0', 'StarCalc 5.0') ### 31
fmts.add('spreadsheet', 'sdc4', 'sdc', 'StarCalc 4.0', 'StarCalc 4.0') ### 11
fmts.add('spreadsheet', 'sdc3', 'sdc', 'StarCalc 3.0', 'StarCalc 3.0') ### 29
fmts.add('spreadsheet', 'slk', 'slk', 'SYLK', 'SYLK') ### 35
fmts.add('spreadsheet', 'stc', 'stc', 'OpenOffice.org 1.0 Spreadsheet Template', 'calc_StarOffice_XML_Calc_Template') ### 2
fmts.add('spreadsheet', 'sxc', 'sxc', 'OpenOffice.org 1.0 Spreadsheet', 'StarOffice XML (Calc)') ### 3
fmts.add('spreadsheet', 'uos', 'uos', 'Unified Office Format spreadsheet', 'UOF spreadsheet') ### 9
fmts.add('spreadsheet', 'vor3', 'vor', 'StarCalc 3.0 Template', 'StarCalc 3.0 Vorlage/Template') ### 18
fmts.add('spreadsheet', 'vor4', 'vor', 'StarCalc 4.0 Template', 'StarCalc 4.0 Vorlage/Template') ### 19
fmts.add('spreadsheet', 'vor', 'vor', 'StarCalc 5.0 Template', 'StarCalc 5.0 Vorlage/Template') ### 20
fmts.add('spreadsheet', 'xhtml', 'xhtml', 'XHTML', 'XHTML Calc File') ### 26
fmts.add('spreadsheet', 'xls', 'xls', 'Microsoft Excel 97/2000/XP', 'MS Excel 97') ### 12
fmts.add('spreadsheet', 'xls5', 'xls', 'Microsoft Excel 5.0', 'MS Excel 5.0/95') ### 8
fmts.add('spreadsheet', 'xls95', 'xls', 'Microsoft Excel 95', 'MS Excel 95') ### 10
fmts.add('spreadsheet', 'xlt', 'xlt', 'Microsoft Excel 97/2000/XP Template', 'MS Excel 97 Vorlage/Template') ### 6
fmts.add('spreadsheet', 'xlt5', 'xlt', 'Microsoft Excel 5.0 Template', 'MS Excel 5.0/95 Vorlage/Template') ### 28
fmts.add('spreadsheet', 'xlt95', 'xlt', 'Microsoft Excel 95 Template', 'MS Excel 95 Vorlage/Template') ### 21

### Graphics
fmts.add('graphics', 'bmp', 'bmp', 'Windows Bitmap', 'draw_bmp_Export') ### 21
fmts.add('graphics', 'emf', 'emf', 'Enhanced Metafile', 'draw_emf_Export') ### 15
fmts.add('graphics', 'eps', 'eps', 'Encapsulated PostScript', 'draw_eps_Export') ### 48
fmts.add('graphics', 'fodg', 'fodg', 'OpenDocument Drawing (Flat XML)', 'OpenDocument Drawing Flat XML')
fmts.add('graphics', 'gif', 'gif', 'Graphics Interchange Format', 'draw_gif_Export') ### 30
fmts.add('graphics', 'html', 'html', 'HTML Document (OpenOffice.org Draw)', 'draw_html_Export') ### 37
fmts.add('graphics', 'jpg', 'jpg', 'Joint Photographic Experts Group', 'draw_jpg_Export') ### 3
fmts.add('graphics', 'met', 'met', 'OS/2 Metafile', 'draw_met_Export') ### 43
fmts.add('graphics', 'odd', 'odd', 'OpenDocument Drawing', 'draw8') ### 6
fmts.add('graphics', 'otg', 'otg', 'OpenDocument Drawing Template', 'draw8_template') ### 20
fmts.add('graphics', 'pbm', 'pbm', 'Portable Bitmap', 'draw_pbm_Export') ### 14
fmts.add('graphics', 'pct', 'pct', 'Mac Pict', 'draw_pct_Export') ### 41
fmts.add('graphics', 'pdf', 'pdf', 'Portable Document Format', 'draw_pdf_Export') ### 28
fmts.add('graphics', 'pgm', 'pgm', 'Portable Graymap', 'draw_pgm_Export') ### 11
fmts.add('graphics', 'png', 'png', 'Portable Network Graphic', 'draw_png_Export') ### 2
fmts.add('graphics', 'ppm', 'ppm', 'Portable Pixelmap', 'draw_ppm_Export') ### 5
fmts.add('graphics', 'ras', 'ras', 'Sun Raster Image', 'draw_ras_Export') ## 31
fmts.add('graphics', 'std', 'std', 'OpenOffice.org 1.0 Drawing Template', 'draw_StarOffice_XML_Draw_Template') ### 53
fmts.add('graphics', 'svg', 'svg', 'Scalable Vector Graphics', 'draw_svg_Export') ### 50
fmts.add('graphics', 'svm', 'svm', 'StarView Metafile', 'draw_svm_Export') ### 55
fmts.add('graphics', 'swf', 'swf', 'Macromedia Flash (SWF)', 'draw_flash_Export') ### 23
fmts.add('graphics', 'sxd', 'sxd', 'OpenOffice.org 1.0 Drawing', 'StarOffice XML (Draw)') ### 26
fmts.add('graphics', 'sxd3', 'sxd', 'StarDraw 3.0', 'StarDraw 3.0') ### 40
fmts.add('graphics', 'sxd5', 'sxd', 'StarDraw 5.0', 'StarDraw 5.0') ### 44
fmts.add('graphics', 'sxw', 'sxw', 'StarOffice XML (Draw)', 'StarOffice XML (Draw)')
fmts.add('graphics', 'tiff', 'tiff', 'Tagged Image File Format', 'draw_tif_Export') ### 13
fmts.add('graphics', 'vor', 'vor', 'StarDraw 5.0 Template', 'StarDraw 5.0 Vorlage') ### 36
fmts.add('graphics', 'vor3', 'vor', 'StarDraw 3.0 Template', 'StarDraw 3.0 Vorlage') ### 35
fmts.add('graphics', 'wmf', 'wmf', 'Windows Metafile', 'draw_wmf_Export') ### 8
fmts.add('graphics', 'xhtml', 'xhtml', 'XHTML', 'XHTML Draw File') ### 45
fmts.add('graphics', 'xpm', 'xpm', 'X PixMap', 'draw_xpm_Export') ### 19

### Presentation
fmts.add('presentation', 'bmp', 'bmp', 'Windows Bitmap', 'impress_bmp_Export') ### 15
fmts.add('presentation', 'emf', 'emf', 'Enhanced Metafile', 'impress_emf_Export') ### 16
fmts.add('presentation', 'eps', 'eps', 'Encapsulated PostScript', 'impress_eps_Export') ### 17
fmts.add('presentation', 'fodp', 'fodp', 'OpenDocument Presentation (Flat XML)', 'OpenDocument Presentation Flat XML')
fmts.add('presentation', 'gif', 'gif', 'Graphics Interchange Format', 'impress_gif_Export') ### 18
fmts.add('presentation', 'html', 'html', 'HTML Document (OpenOffice.org Impress)', 'impress_html_Export') ### 43
fmts.add('presentation', 'jpg', 'jpg', 'Joint Photographic Experts Group', 'impress_jpg_Export') ### 19
fmts.add('presentation', 'met', 'met', 'OS/2 Metafile', 'impress_met_Export') ### 20
fmts.add('presentation', 'odg', 'odg', 'ODF Drawing (Impress)', 'impress8_draw') ### 29
fmts.add('presentation', 'odp', 'odp', 'ODF Presentation', 'impress8') ### 9
fmts.add('presentation', 'otp', 'otp', 'ODF Presentation Template', 'impress8_template') ### 38
fmts.add('presentation', 'pbm', 'pbm', 'Portable Bitmap', 'impress_pbm_Export') ### 21
fmts.add('presentation', 'pct', 'pct', 'Mac Pict', 'impress_pct_Export') ### 22
fmts.add('presentation', 'pdf', 'pdf', 'Portable Document Format', 'impress_pdf_Export') ### 23
fmts.add('presentation', 'pgm', 'pgm', 'Portable Graymap', 'impress_pgm_Export') ### 24
fmts.add('presentation', 'png', 'png', 'Portable Network Graphic', 'impress_png_Export') ### 25
fmts.add('presentation', 'potm', 'potm', 'Microsoft PowerPoint 2007/2010 XML Template', 'Impress MS PowerPoint 2007 XML Template')
fmts.add('presentation', 'pot', 'pot', 'Microsoft PowerPoint 97/2000/XP Template', 'MS PowerPoint 97 Vorlage') ### 3
fmts.add('presentation', 'ppm', 'ppm', 'Portable Pixelmap', 'impress_ppm_Export') ### 26
fmts.add('presentation', 'pptx', 'pptx', 'Microsoft PowerPoint 2007/2010 XML', 'Impress MS PowerPoint 2007 XML') ### 36
fmts.add('presentation', 'pps', 'pps', 'Microsoft PowerPoint 97/2000/XP (Autoplay)', 'MS PowerPoint 97 Autoplay') ### 36
fmts.add('presentation', 'ppt', 'ppt', 'Microsoft PowerPoint 97/2000/XP', 'MS PowerPoint 97') ### 36
fmts.add('presentation', 'pwp', 'pwp', 'PlaceWare', 'placeware_Export') ### 30
fmts.add('presentation', 'ras', 'ras', 'Sun Raster Image', 'impress_ras_Export') ### 27
fmts.add('presentation', 'sda', 'sda', 'StarDraw 5.0 (OpenOffice.org Impress)', 'StarDraw 5.0 (StarImpress)') ### 8
fmts.add('presentation', 'sdd', 'sdd', 'StarImpress 5.0', 'StarImpress 5.0') ### 6
fmts.add('presentation', 'sdd3', 'sdd', 'StarDraw 3.0 (OpenOffice.org Impress)', 'StarDraw 3.0 (StarImpress)') ### 42
fmts.add('presentation', 'sdd4', 'sdd', 'StarImpress 4.0', 'StarImpress 4.0') ### 37
fmts.add('presentation', 'sxd', 'sxd', 'OpenOffice.org 1.0 Drawing (OpenOffice.org Impress)', 'impress_StarOffice_XML_Draw') ### 31
fmts.add('presentation', 'sti', 'sti', 'OpenOffice.org 1.0 Presentation Template', 'impress_StarOffice_XML_Impress_Template') ### 5
fmts.add('presentation', 'svg', 'svg', 'Scalable Vector Graphics', 'impress_svg_Export') ### 14
fmts.add('presentation', 'svm', 'svm', 'StarView Metafile', 'impress_svm_Export') ### 13
fmts.add('presentation', 'swf', 'swf', 'Macromedia Flash (SWF)', 'impress_flash_Export') ### 34
fmts.add('presentation', 'sxi', 'sxi', 'OpenOffice.org 1.0 Presentation', 'StarOffice XML (Impress)') ### 41
fmts.add('presentation', 'tiff', 'tiff', 'Tagged Image File Format', 'impress_tif_Export') ### 12
fmts.add('presentation', 'uop', 'uop', 'Unified Office Format presentation', 'UOF presentation') ### 4
fmts.add('presentation', 'vor', 'vor', 'StarImpress 5.0 Template', 'StarImpress 5.0 Vorlage') ### 40
fmts.add('presentation', 'vor3', 'vor', 'StarDraw 3.0 Template (OpenOffice.org Impress)', 'StarDraw 3.0 Vorlage (StarImpress)') ###1
fmts.add('presentation', 'vor4', 'vor', 'StarImpress 4.0 Template', 'StarImpress 4.0 Vorlage') ### 39
fmts.add('presentation', 'vor5', 'vor', 'StarDraw 5.0 Template (OpenOffice.org Impress)', 'StarDraw 5.0 Vorlage (StarImpress)') ### 2
fmts.add('presentation', 'wmf', 'wmf', 'Windows Metafile', 'impress_wmf_Export') ### 11
fmts.add('presentation', 'xhtml', 'xml', 'XHTML', 'XHTML Impress File') ### 33
fmts.add('presentation', 'xpm', 'xpm', 'X PixMap', 'impress_xpm_Export') ### 10

class Options:
    def __init__(self, args):
        self.connection = None
        self.doctype = None
        self.exportfilter = []
        self.filenames = []
        self.format = None
        self.importfilter = ""
        self.listener = False
        self.nolaunch = False
        self.output = None
        self.pipe = None
        self.port = '2002'
        self.server = 'localhost'
        self.showlist = False
        self.stdout = False
        self.template = None
        self.timeout = 6
        self.verbose = 0

        ### Get options from the commandline
        try:
            opts, args = getopt.getopt (args, 'c:Dd:e:f:hi:Llo:np:s:T:t:v',
                ['connection=', 'doctype=', 'export', 'format=', 'help',
                 'import', 'listener', 'no-launch', 'output=', 'outputpath',
                 'pipe=', 'port=', 'server=', 'timeout=', 'show', 'stdout',
                 'template', 'verbose', 'version'] )
        except getopt.error, exc:
            print 'unoconv: %s, try unoconv -h for a list of all the options' % str(exc)
            sys.exit(255)

        for opt, arg in opts:
            if opt in ['-h', '--help']:
                self.usage()
                print
                self.help()
                sys.exit(1)
            elif opt in ['-c', '--connection']:
                self.connection = arg
            elif opt in ['-d', '--doctype']:
                self.doctype = arg
            elif opt in ['-e', '--export']:
                l = arg.split('=')
                if len(l) == 2:
                    (name, value) = l
                    if value in ('True', 'true'):
                        self.exportfilter.append( PropertyValue( name, 0, True, 0 ) )
                    elif value in ('False', 'false'):
                        self.exportfilter.append( PropertyValue( name, 0, False, 0 ) )
                    else:
                        try:
                            self.exportfilter.append( PropertyValue( name, 0, int(value), 0 ) )
                        except ValueError:
                            self.exportfilter.append( PropertyValue( name, 0, value, 0 ) )
                else:
#                    print >>sys.stderr, 'Warning: Option %s cannot be parsed, ignoring.' % arg
                    self.importfilter = arg
            elif opt in ['-f', '--format']:
                self.format = arg
            elif opt in ['-i', '--import']:
                self.importfilter = arg
            elif opt in ['-l', '--listener']:
                self.listener = True
            elif opt in ['-n', '--no-launch']:
                self.nolaunch = True
            elif opt in ['-o', '--output']:
                self.output = arg
            elif opt in ['--outputpath']:
                print >>sys.stderr, 'Warning: This option is deprecated by --output.'
                self.output = arg
            elif opt in ['--pipe']:
                self.pipe = arg
            elif opt in ['-p', '--port']:
                self.port = arg
            elif opt in ['-s', '--server']:
                self.server = arg
            elif opt in ['--show']:
                self.showlist = True
            elif opt in ['--stdout']:
                self.stdout = True
            elif opt in ['-t', '--template']:
                self.template = arg
            elif opt in ['-T', '--timeout']:
                self.timeout = int(arg)
            elif opt in ['-v', '--verbose']:
                self.verbose = self.verbose + 1
            elif opt in ['--version']:
                self.version()
                sys.exit(255)

        ### Enable verbosity
        if self.verbose >= 3:
            print >>sys.stderr, 'Verbosity set to level %d' % (self.verbose - 1)

        self.filenames = args

        if not self.listener and not self.showlist and self.doctype != 'list' and not self.filenames:
            print >>sys.stderr, 'unoconv: you have to provide a filename as argument'
            print >>sys.stderr, 'Try `unoconv -h\' for more information.'
            sys.exit(255)

        ### Set connection string
        if not self.connection:
            if not self.pipe:
                self.connection = "socket,host=%s,port=%s;urp;StarOffice.ComponentContext" % (self.server, self.port)
#               self.connection = "socket,host=%s,port=%s;urp;" % (self.server, self.port)
            else:
                self.connection = "pipe,name=%s;urp;StarOffice.ComponentContext" % (self.pipe)
            if self.verbose >=3:
                print >>sys.stderr, 'Connection type: %s' % self.connection

        ### Make it easier for people to use a doctype (first letter is enough)
        if self.doctype:
            for doctype in doctypes:
                if doctype.startswith(self.doctype):
                    self.doctype = doctype

        ### Check if the user request to see the list of formats
        if self.showlist or self.format == 'list':
            if self.doctype:
                fmts.display(self.doctype)
            else:
                for t in doctypes:
                    fmts.display(t)
            sys.exit(0)

        ### If no format was specified, probe it or provide it
        if not self.format:
            l = sys.argv[0].split('2')
            if len(l) == 2:
                self.format = l[1]
            else:
                self.format = 'pdf'

    def version(self):
        ### Get office product information
        product = uno.getComponentContext().ServiceManager.createInstance("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", UnoProps(nodepath="/org.openoffice.Setup/Product"))

        print 'unoconv %s' % VERSION
        print 'Written by Dag Wieers <dag@wieers.com>'
        print 'Homepage at http://dag.wieers.com/home-made/unoconv/'
        print
        print 'platform %s/%s' % (os.name, sys.platform)
        print 'python %s' % sys.version
        print product.ooName, product.ooSetupVersion
        print
        print 'build revision $Rev$'

    def usage(self):
        print >>sys.stderr, 'usage: unoconv [options] file [file2 ..]'

    def help(self):
        print >>sys.stderr, '''Convert from and to any format supported by LibreOffice

unoconv options:
  -c, --connection=string  use a custom connection string
  -d, --doctype=type       specify document type
                             (document, graphics, presentation, spreadsheet)
  -e, --export=name=value  set export filter options
                             eg. -e PageRange=1-2
  -f, --format=format      specify the output format
  -i, --import=string      set import filter option string
                             eg. -i utf8
  -l, --listener           start a permanent listener to use by unoconv clients
  -n, --no-launch          fail if no listener is found (default: launch one)
  -o, --output=name        output basename, filename or directory
      --pipe=name          alternative method of connection using a pipe
  -p, --port=port          specify the port (default: 2002)
                             to be used by client or listener
  -s, --server=server      specify the server address (default: localhost)
                             to be used by client or listener
      --show               list the available output formats
      --stdout             write output to stdout
  -t, --template=file      import the styles from template (.ott)
  -T, --timeout=secs       timeout after secs if connection to listener fails
  -v, --verbose            be more and more verbose
'''

class Convertor:
    def __init__(self):
        global exitcode, ooproc, office, product
        unocontext = None

        ### Do the LibreOffice component dance
        self.context = uno.getComponentContext()
        self.svcmgr = self.context.ServiceManager
        resolver = self.svcmgr.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", self.context)

        ### Test for an existing connection
        try:
            unocontext = resolver.resolve("uno:%s" % op.connection)
        except NoConnectException, e:
#            info(3, "Existing listener not found.\n%s" % e)
            info(3, "Existing listener not found.")

            if op.nolaunch:
                die(113, "Existing listener not found. Unable start listener by parameters. Aborting.")

            ### Start our own OpenOffice instance
            info(3, "Launching our own listener using %s." % office.binary)
            try:
                product = self.svcmgr.createInstance("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", UnoProps(nodepath="/org.openoffice.Setup/Product"))
                if product.ooName != "LibreOffice" or product.ooSetupVersion <= 3.3:
                    ooproc = subprocess.Popen([office.binary, "-headless", "-invisible", "-nocrashreport", "-nodefault", "-nofirststartwizard", "-nologo", "-norestore", "-accept=%s" % op.connection], env=os.environ)
                else:
                    ooproc = subprocess.Popen([office.binary, "--headless", "--invisible", "--nocrashreport", "--nodefault", "--nofirststartwizard", "--nologo", "--norestore", "--accept=%s" % op.connection], env=os.environ)
                info(2, '%s listener successfully started. (pid=%s)' % (product.ooName, ooproc.pid))

                ### Try connection to it for op.timeout seconds (flakky OpenOffice)
                timeout = 0
                while timeout <= op.timeout:
                    ### Is it already/still running ?
                    retcode = ooproc.poll()
                    if retcode != None:
                        info(3, "Process %s (pid=%s) exited with %s." % (office.binary, ooproc.pid, retcode))
                        break
                    try:
                        unocontext = resolver.resolve("uno:%s" % op.connection)
                        break
                    except NoConnectException:
                        time.sleep(0.5)
                        timeout += 0.5
                    except:
                        raise
                else:
                    error("Failed to connect to %s (pid=%s) in %d seconds.\n%s" % (office.binary, ooproc.pid, op.timeout, e))
            except Exception, e:
                raise
                error("Launch of %s failed.\n%s" % (office.binary, e))

        if not unocontext:
            die(251, "Unable to connect or start own listener. Aborting.")

        ### And some more LibreOffice magic
        unosvcmgr = unocontext.ServiceManager
        self.desktop = unosvcmgr.createInstanceWithContext("com.sun.star.frame.Desktop", unocontext)
        self.cwd = unohelper.systemPathToFileUrl( os.getcwd() )

        ### List all filters
#        self.filters = unosvcmgr.createInstanceWithContext( "com.sun.star.document.FilterFactory", unocontext)
#        for filter in self.filters.getElementNames():
#            print filter
#            #print dir(filter), dir(filter.format)

    def getformat(self, inputfn):
        doctype = None

        ### Get the output format from mapping
        if op.doctype:
            outputfmt = fmts.bydoctype(op.doctype, op.format)
        else:
            outputfmt = fmts.byname(op.format)

            if not outputfmt:
                outputfmt = fmts.byextension(os.extsep + op.format)

        ### If no doctype given, check list of acceptable formats for input file ext doctype
        ### FIXME: This should go into the for-loop to match each individual input filename
        if outputfmt:
            inputext = os.path.splitext(inputfn)[1]
            inputfmt = fmts.byextension(inputext)
            if inputfmt:
                for fmt in outputfmt:
                    if inputfmt[0].doctype == fmt.doctype:
                        doctype = inputfmt[0].doctype
                        outputfmt = fmt
                        break
                else:
                    outputfmt = outputfmt[0]
    #       print >>sys.stderr, 'unoconv: format `%s\' is part of multiple doctypes %s, selecting `%s\'.' % (format, [fmt.doctype for fmt in outputfmt], outputfmt[0].doctype)
            else:
                outputfmt = outputfmt[0]

        ### No format found, throw error
        if not outputfmt:
            if doctype:
                print >>sys.stderr, 'unoconv: format [%s/%s] is not known to unoconv.' % (op.doctype, op.format)
            else:
                print >>sys.stderr, 'unoconv: format [%s] is not known to unoconv.' % op.format
            die(1)

        return outputfmt

    def convert(self, inputfn):
        global exitcode

        document = None
        outputfmt = self.getformat(inputfn)

        if op.verbose > 0:
            print >>sys.stderr, 'Input file:', inputfn

        if not os.path.exists(inputfn):
            print >>sys.stderr, 'unoconv: file `%s\' does not exist.' % inputfn
            exitcode = 1

        try:
            ### Import phase
            phase = "import"

            ### Load inputfile
            inputprops = UnoProps(Hidden=True, ReadOnly=True, UpdateDocMode=QUIET_UPDATE, FilterOptions=op.importfilter)
            inputurl = unohelper.absolutize(self.cwd, unohelper.systemPathToFileUrl(inputfn))
#            print dir(self.desktop)
            document = self.desktop.loadComponentFromURL( inputurl , "_blank", 0, inputprops )

            if not document:
                raise UnoException("The document '%s' could not be opened." % inputurl, None)

            ### Import style template
            phase = "import-style"
            if op.template:
                if os.path.exists(op.template):
                    info(1, "Template file: %s" % op.template)
                    templateprops = UnoProps(OverwriteStyles=True)
                    templateurl = unohelper.absolutize(self.cwd, unohelper.systemPathToFileUrl(op.template))
                    document.StyleFamilies.loadStylesFromURL(templateurl, templateprops)
                else:
                    print >>sys.stderr, 'unoconv: template file `%s\' does not exist.' % op.template
                    exitcode = 1

            ### Update document links
            phase = "update-links"
            try:
                document.updateLinks()
            except AttributeError:
                # the document doesn't implement the XLinkUpdate interface
                pass

            ### Update document indexes
            phase = "update-indexes"
            try:
                document.refresh()
                indexes = document.getDocumentIndexes()
            except AttributeError:
                # the document doesn't implement the XRefreshable and/or
                # XDocumentIndexesSupplier interfaces
                pass
            else:
                for i in range(0, indexes.getCount()):
                    indexes.getByIndex(i).update()

            info(1, "Selected output format: %s" % outputfmt)
            info(1, "Selected office filter: %s" % outputfmt.filter)
            info(1, "Used doctype: %s" % outputfmt.doctype)

            ### Export phase
            phase = "export"
            outputprops = UnoProps(FilterName=outputfmt.filter, OutputStream=OutputStream(), Overwrite=True, FilterData=tuple( op.exportfilter) )
#                PropertyValue( "FilterData" , 0, ( PropertyValue( "SelectPdfVersion" , 0, 1 , uno.getConstantByName( "com.sun.star.beans.PropertyState.DIRECT_VALUE" ) ) ), uno.getConstantByName( "com.sun.star.beans.PropertyState.DIRECT_VALUE" ) ),

            if outputfmt.filter == 'Text (encoded)':
                outputprops += UnoProps(FilterOptions="UTF8, LF")

            elif outputfmt.filter == 'Text':
                outputprops += UnoProps(FilterOptions="UTF8")

            elif outputfmt.filter == 'Text - txt - csv (StarCalc)':
                outputprops += UnoProps(FilterOptions="44,34,0")

            if not op.stdout:
                (outputfn, ext) = os.path.splitext(inputfn)
                if not op.output:
                    outputfn = outputfn + os.extsep + outputfmt.extension
                elif os.path.isdir(op.output):
                    outputfn = os.path.join(op.output, os.path.basename(outputfn) + os.extsep + outputfmt.extension)
                elif len(op.filenames) > 1:
                    outputfn = op.output + os.extsep + outputfmt.extension
                else:
                    outputfn = op.output

                outputurl = unohelper.absolutize( self.cwd, unohelper.systemPathToFileUrl(outputfn) )
                info(1, "Output file: %s" % outputfn)
            else:
                outputurl = "private:stream"

            try:
                document.storeToURL(outputurl, tuple(outputprops) )
            except IOException, e:
                raise UnoException("Unable to store document to %s with properties %s. Exception: %s" % (outputurl, outputprops, e), None)

            phase = "dispose"
            document.dispose()
            document.close(True)

        except SystemError, e:
            error("unoconv: SystemError during %s phase: %s" % (phase, e))
            exitcode = 1

        except RuntimeException, e:
            error("unoconv: RuntimeException during %s phase: Office probably died. %s" % (phase, e))
            exitcode = 6

        except DisposedException, e:
            error("unoconv: DisposedException during %s phase: Office probably died. %s" % (phase, e))
            exitcode = 7

        except IllegalArgumentException, e:
            error("UNO IllegalArgument during %s phase: Source file cannot be read. %s" % (phase, e))
            exitcode = 8

        except IOException, e:
#            for attr in dir(e): print '%s: %s', (attr, getattr(e, attr))
            error("unoconv: IOException during %s phase: %s" % (phase, e.Message))
            exitcode = 3

        except CannotConvertException, e:
#            for attr in dir(e): print '%s: %s', (attr, getattr(e, attr))
            error("unoconv: CannotConvertException during %s phase: %s" % (phase, e.Message))
            exitcode = 4

        except UnoException, e:
            if hasattr(e, 'ErrCode'):
                error("unoconv: UnoException during %s phase in %s (ErrCode %d)" % (phase, repr(e.__class__), e.ErrCode))
                exitcode = e.ErrCode
                pass
            if hasattr(e, 'Message'):
                error("unoconv: UnoException during %s phase: %s" % (phase, e.Message))
                exitcode = 5
            else:
                error("unoconv: UnoException during %s phase in %s" % (phase, repr(e.__class__)))
                exitcode = 2
                pass

class Listener:
    def __init__(self):
        global product

        info(1, "Start listener on %s:%s" % (op.server, op.port))
        self.context = uno.getComponentContext()
        self.svcmgr = self.context.ServiceManager
        try:
            product = self.svcmgr.createInstance("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", UnoProps(nodepath="/org.openoffice.Setup/Product"))
            if product.ooName != "LibreOffice" or product.ooSetupVersion <= 3.3:
                subprocess.call([office.binary, "-headless", "-invisible", "-nocrashreport", "-nodefault", "-nologo", "-nofirststartwizard", "-norestore", "-accept=%s" % op.connection], env=os.environ)
            else:
                subprocess.call([office.binary, "--headless", "--invisible", "--nocrashreport", "--nodefault", "--nologo", "--nofirststartwizard", "--norestore", "--accept=%s" % op.connection], env=os.environ)
        except Exception, e:
            error("Launch of %s failed.\n%s" % (office.binary, e))
        else:
            info(1, "Existing %s listener found, nothing to do." % product.ooName)

def error(str):
    "Output error message"
    print >>sys.stderr, str

def info(level, str):
    "Output info message"
    if not op.stdout and level <= op.verbose:
        print >>sys.stdout, str
    elif level <= op.verbose:
        print >>sys.stderr, str

def die(ret, str=None):
    "Print optional error and exit with errorcode"
    global convertor, ooproc, office

    if str:
        error('Error: %s' % str)

    ### Did we start our own listener instance ?
    if not op.listener and ooproc and convertor:

        ### If there is a GUI now attached to the instance, disable listener
        if convertor.desktop.getCurrentFrame():
            info(2, 'Trying to stop %s GUI listener.' % product.ooName)
            try:
                if product.ooName != "LibreOffice" or product.ooSetupVersion <= 3.3:
                    subprocess.Popen([office.binary, "-headless", "-invisible", "-nocrashreport", "-nodefault", "-nofirststartwizard", "-nologo", "-norestore", "-unaccept=%s" % op.connection], env=os.environ)
                else:
                    subprocess.Popen([office.binary, "--headless", "--invisible", "--nocrashreport", "--nodefault", "--nofirststartwizard", "--nologo", "--norestore", "--unaccept=%s" % op.connection], env=os.environ)
                ooproc.wait()
                info(2, '%s listener successfully disabled.' % product.ooName)
            except Exception, e:
                error("Terminate using %s failed.\n%s" % (office.binary, e))

        ### If there is no GUI attached to the instance, terminate instance
        else:
            info(3, 'Terminating %s instance.' % product.ooName)
            try:
                convertor.desktop.terminate()
            except DisposedException:
                info(2, '%s instance unsuccessfully closed, sending TERM signal.' % product.ooName)
                try:
                    ooproc.terminate()
                except AttributeError:
                    os.kill(ooproc.pid, 15)
            info(3, 'Waiting for %s instance to exit.' % product.ooName)
            ooproc.wait()

        ### LibreOffice processes may get stuck and we have to kill them
        ### Is it still running ?
        if ooproc.poll() == None:
            info(1, '%s instance still running, please investigate...' % product.ooName)
            ooproc.wait()
            info(2, '%s instance unsuccessfully terminated, sending KILL signal.' % product.ooName)
            try:
                ooproc.kill()
            except AttributeError:
                os.kill(ooproc.pid, 9)
            info(3, 'Waiting for %s with pid %s to disappear.' % (ooproc.pid, product.ooName))
            ooproc.wait()

    sys.exit(ret)

def main():
    global convertor, exitcode
    convertor = None

    try:
        if op.listener:
            listener = Listener()

        if op.filenames:
            convertor = Convertor()
            for inputfn in op.filenames:
                convertor.convert(inputfn)

    except NoConnectException, e:
        error("unoconv: could not find an existing connection to LibreOffice at %s:%s." % (op.server, op.port))
        if op.connection:
            info(0, "Please start an LibreOffice instance on server '%s' by doing:\n\n    unoconv --listener --server %s --port %s\n\nor alternatively:\n\n    soffice -nologo -nodefault -accept=\"%s\"" % (op.server, op.server, op.port, op.connection))
        else:
            info(0, "Please start an LibreOffice instance on server '%s' by doing:\n\n    unoconv --listener --server %s --port %s\n\nor alternatively:\n\n    soffice -nologo -nodefault -accept=\"socket,host=%s,port=%s;urp;\"" % (op.server, op.server, op.port, op.server, op.port))
            info(0, "Please start an soffice instance on server '%s' by doing:\n\n    soffice -nologo -nodefault -accept=\"socket,host=localhost,port=%s;urp;\"" % (op.server, op.port))
        exitcode = 1
#    except UnboundLocalError:
#        die(252, "Failed to connect to remote listener.")
    except OSError:
        error("Warning: failed to launch Office suite. Aborting.")

### Main entrance
if True or __name__ == '__main__': ## always pass here
    exitcode = 0

    for of in find_offices():
        if of.python != sys.executable and not sys.executable.startswith(of.unopath):
            python_switch(of)
        office_environ(of)
#        debug_office()
        try:
            import uno, unohelper
            office = of
            break
        except:
            print >>sys.stderr, "unoconv: Cannot find a suitable pyuno library and python binary combination in %s" % of
            print >>sys.stderr, "ERROR: Please locate this library and send your feedback to:"
            print >>sys.stderr, "       http://github.com/dagwieers/unoconv/issues"
            print >>sys.stderr, sys.exc_info()[1]
            pass
    else:
        print >>sys.stderr, "unoconv: Cannot find a suitable office installation on your system."
        print >>sys.stderr, "ERROR: Please locate your office installation and send your feedback to:"
        print >>sys.stderr, "       http://github.com/dagwieers/unoconv/issues"
        sys.exit(1)

    ### Now that we have found a working pyuno library, let's import some classes
    from com.sun.star.beans import PropertyValue
    from com.sun.star.connection import NoConnectException
    from com.sun.star.document.UpdateDocMode import QUIET_UPDATE
    from com.sun.star.lang import DisposedException, IllegalArgumentException
    from com.sun.star.io import IOException, XOutputStream
    from com.sun.star.script import CannotConvertException
    from com.sun.star.uno import Exception as UnoException
    from com.sun.star.uno import RuntimeException

    ### And now that we have those classes, build on them
    class OutputStream( unohelper.Base, XOutputStream ):
        def __init__( self ):
            self.closed = 0

        def closeOutput(self):
            self.closed = 1

        def writeBytes( self, seq ):
            sys.stdout.write( seq.value )

        def flush( self ):
            pass

    def UnoProps(**args):
        props = []
        for key in args:
            prop = PropertyValue()
            prop.Name = key
            prop.Value = args[key]
            props.append(prop)
        return tuple(props)

    op = Options(sys.argv[1:])

    info(2, "Office base location: %s" % office.basepath)
    info(2, "Office binary location: %s" % office.unopath)

if __name__ == '__main__': ## never pass here
    try:
        main()
    except KeyboardInterrupt, e:
        die(6, 'Exiting on user request')
    die(exitcode)
