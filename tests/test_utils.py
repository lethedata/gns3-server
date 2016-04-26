#!/usr/bin/env python
#
# Copyright (C) 2015 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from gns3server.utils import force_unix_path, macaddress_to_int, int_to_macaddress


def test_force_unix_path():
    assert force_unix_path("a/b") == "a/b"
    assert force_unix_path("a\\b") == "a/b"
    assert force_unix_path("a\\b\\..\\c") == "a/c"


def test_macaddress_to_int():
    assert macaddress_to_int("00:0c:29:11:b0:0a") == 52228632586


def test_int_to_macaddress():
    assert int_to_macaddress(52228632586) == "00:0c:29:11:b0:0a"
