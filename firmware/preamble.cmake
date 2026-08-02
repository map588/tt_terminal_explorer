# Board and SDK setup for the Tiny Tapeout demo board v3.
#
# Include this FIRST in a CMakeLists, before project(). It sets the
# board (RP2350B, tt_dbv3), the platform, and imports the pico-sdk.
# The order matters and this file owns it, so an extension project
# starts with:
#
#   cmake_minimum_required(VERSION 3.13)
#   include(<path-to-kit>/firmware/preamble.cmake)
#   project(my_project C CXX ASM)
#   pico_sdk_init()
#   include(<path-to-kit>/firmware/core.cmake)
#   ...

list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
set(PICO_BOARD tt_dbv3 CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform")

include(${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake)
