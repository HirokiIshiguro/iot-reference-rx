# GCC for Renesas RX (14.2.x) 用 CMake ツールチェインファイル。
# GCC は CMake が GNU として自動認識するので、コンパイラパスと
# ターゲットフラグのみを指定する。
#
#   -DRX_GCC_BIN=<...> でツールチェイン bin を上書き可能。

set(CMAKE_SYSTEM_NAME      Generic)
set(CMAKE_SYSTEM_PROCESSOR rx)

if(NOT DEFINED RX_GCC_BIN)
    set(RX_GCC_BIN "C:/ProgramData/GCC for Renesas RX 14.2.0.202511-GNURX-ELF/rx-elf/rx-elf/bin")
endif()

set(CMAKE_C_COMPILER   "${RX_GCC_BIN}/rx-elf-gcc.exe")
set(CMAKE_ASM_COMPILER "${RX_GCC_BIN}/rx-elf-gcc.exe")

# ベアメタル: コンパイラ検査は実行ファイルでなく静的ライブラリで行う
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_C_FLAGS_INIT "-misa=v2 -mlittle-endian-data")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
