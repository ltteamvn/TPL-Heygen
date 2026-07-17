# file: nuitka_imports.py
# Muc dich: Khai bao import tat ca cac thu vien chuan (Standard Library) cua Python
# de Nuitka phan tich va tu dong dong goi day du vao file EXE.
# Viec nay cuc ky quan trong vi chung ta dang su dung --nofollow-import-to
# cho cac thu vien ngoai nhu requests, selenium, PySide6...
# Khong co file nay, cac thu vien ngoai se bi loi thieu Standard Library o runtime.

# --- urllib & http ---
import urllib.request
import urllib.parse
import urllib.error
import urllib.response
import urllib.robotparser
import http.client
import http.cookies
import http.cookiejar
import http.server

# --- HTML & XML ---
import html
import html.parser
import html.entities
import xml
import xml.etree.ElementTree
import xml.parsers.expat
import xml.sax
import xml.sax.expatreader
import xml.dom
import xml.dom.minidom

# --- Network & SSL ---
import ssl
import socket
import select
import selectors

# --- Email (rat quan trong cho requests/urllib3 parse headers) ---
import email
import email.message
import email.parser
import email.utils
import email.errors
import email.feedparser
import email.mime.text
import email.mime.multipart

# --- System & OS & Utility ---
import ctypes
import ctypes.wintypes
import sqlite3
import hashlib
import hmac
import uuid
import json
import csv
import configparser
import logging
import logging.config
import logging.handlers
import queue
import getpass
import netrc
import plistlib
import tarfile
import zipfile
import tempfile
import pkgutil
import importlib
import importlib.metadata

# --- Multiprocessing & Concurrency ---
import multiprocessing
import multiprocessing.connection
import multiprocessing.pool
import multiprocessing.sharedctypes
import concurrent.futures
import threading

# --- Unittest (can thiet cho mot so package) ---
import unittest
import unittest.mock

# --- Debugging (can thiet cho torch) ---
import pdb
import bdb
import cmd

