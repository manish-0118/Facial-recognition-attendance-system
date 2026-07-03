# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NihareekaAttendance
# Build: pyinstaller NihareekaAttendance.spec

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect customtkinter themes/images
ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('models/*.onnx',                         'models'),
        ('cascades/haarcascade_frontalface_default.xml', 'cascades'),
        ('assets/favicon.ico',                    'assets'),
        *ctk_datas,
    ],
    hiddenimports=[
        # xml — required by pkg_resources at runtime
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        'xml.parsers',
        'xml.parsers.expat',
        # mysql connector
        'mysql.connector',
        'mysql.connector.plugins',
        'mysql.connector.plugins.mysql_native_password',
        'mysql.connector.plugins.caching_sha2_password',
        # cv2 / numpy
        'cv2',
        'numpy',
        # PIL / matplotlib
        'PIL._tkinter_finder',
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        # reportlab
        'reportlab',
        'reportlab.lib.colors',
        'reportlab.lib.pagesizes',
        'reportlab.platypus',
        'reportlab.pdfgen',
        # openpyxl
        'openpyxl',
        # customtkinter
        'customtkinter',
        # app modules
        'setup_db',
        'core.config',
        'core.database',
        'core.errors',
        'core.face_engine',
        'core.logger',
        'core.mariadb_manager',
        'core.paths',
        'core.scheduler',
        'take_attendance',
        'gui.app',
        'gui.admin_page',
        'gui.archive_page',
        'gui.attendance_page',
        'gui.audit_page',
        'gui.class_hub_page',
        'gui.dashboard_page',
        'gui.export_page',
        'gui.login_page',
        'gui.register_page',
        'gui.settings_page',
        'gui.theme',
        'gui.widgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NihareekaAttendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # windowed — no console flash on launch
    icon='assets/favicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NihareekaAttendance',
)
