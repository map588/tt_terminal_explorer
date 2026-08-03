cmake_minimum_required(VERSION 3.13)

# In your own repo, point these two includes at the kit submodule,
# for example kit/firmware/preamble.cmake and kit/firmware/core.cmake.
include(../preamble.cmake)

project(blink_example C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

include(../core.cmake)

tt_extension(tt_host blink_ext.c)
