cmake_minimum_required(VERSION 3.20)

# ============================================================================
# aws_ether_ck_rx65n_v2 ファームウェアの CMake ビルド（CC-RX / GCC for RX 両対応）
#
# e2 studio の managed-make が生成する compile_commands.json から抽出した
# ソース・インクルード・定義を sources_<tc>.cmake に格納し、各ツールチェインの
# ネイティブツールで実機ファーム(.mot)までビルドする。
#
#   # GCC
#   cmake -S . -B build_gcc  -G "Unix Makefiles" \
#         -DCMAKE_MAKE_PROGRAM=<gnu-make> \
#         -DCMAKE_TOOLCHAIN_FILE=../../../cmake/toolchain-gccrx.cmake
#   cmake --build build_gcc
#
#   # CC-RX
#   cmake -S . -B build_ccrx -G "Unix Makefiles" \
#         -DCMAKE_MAKE_PROGRAM=<gnu-make> \
#         -DCMAKE_TOOLCHAIN_FILE=../../../cmake/toolchain-ccrx.cmake
#   cmake --build build_ccrx
# ============================================================================

project(aws_ether_ck_rx65n_v2 C)

get_filename_component(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
set(FW_NAME "aws_ether_ck_rx65n_v2")

set(MBEDTLS_CFG "aws_mbedtls_config.h")

if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
    set(RX_TC gcc)
else()
    set(RX_TC ccrx)
endif()
message(STATUS "RX firmware build: toolchain=${RX_TC} compiler=${CMAKE_C_COMPILER}")

# 抽出済みソース/インクルード/定義（repo相対）
include(${CMAKE_CURRENT_SOURCE_DIR}/sources_${RX_TC}.cmake)

# repo相対 → 絶対パスへ
set(_srcs "")
foreach(s ${FW_SOURCES})
    list(APPEND _srcs "${REPO_ROOT}/${s}")
endforeach()
set(_incs "")
foreach(i ${FW_INCLUDES})
    list(APPEND _incs "${REPO_ROOT}/${i}")
endforeach()

# ===========================================================================
if(RX_TC STREQUAL "gcc")
# ===========================================================================
    enable_language(ASM)
    set(_reset_asm "${REPO_ROOT}/Projects/${FW_NAME}/e2studio_gcc/src/smc_gen/r_bsp/mcu/all/reset_program.S")

    add_executable(${FW_NAME} ${_srcs} ${_reset_asm})
    set_target_properties(${FW_NAME} PROPERTIES OUTPUT_NAME "${FW_NAME}" SUFFIX ".elf")
    target_include_directories(${FW_NAME} PRIVATE ${_incs})
    target_compile_definitions(${FW_NAME} PRIVATE
        ${FW_DEFINES} MBEDTLS_CONFIG_FILE="${MBEDTLS_CFG}")
    # -std=gnu99 は e2 studio プロジェクトの指定。GCC14 は implicit 宣言を既定で
    # エラー化するため、念のため warning へ降格（memset 等は libc で解決される）。
    target_compile_options(${FW_NAME} PRIVATE
        $<$<COMPILE_LANGUAGE:C>:-std=gnu99;-Og;-ffunction-sections;-fdata-sections;-fno-strict-aliasing;-Wstack-usage=2000;-g2;-Wno-error=implicit-function-declaration;-Wno-error=incompatible-pointer-types;-Wno-error=int-conversion>)
    set(CMAKE_ASM_FLAGS "-misa=v2 -mlittle-endian-data -g2")

    # リンカスクリプトは相対 INCLUDE を含むので絶対パスへ書換えたパッチ版を使う
    set(_ld_src "${REPO_ROOT}/Projects/${FW_NAME}/e2studio_gcc/src/linker_script.ld")
    set(_ld_patched "${CMAKE_CURRENT_BINARY_DIR}/linker_script.patched.ld")
    file(READ "${_ld_src}" _ld_text)
    string(REPLACE "../src/" "${REPO_ROOT}/Projects/${FW_NAME}/e2studio_gcc/src/" _ld_text "${_ld_text}")
    file(WRITE "${_ld_patched}" "${_ld_text}")

    target_link_options(${FW_NAME} PRIVATE
        -misa=v2 -mlittle-endian-data -nostartfiles
        -T "${_ld_patched}"
        -Wl,-e_PowerON_Reset -Wl,--gc-sections
        -Wl,-Map=${FW_NAME}.map
        -Wl,--start-group -lm -lc -lgcc -Wl,--end-group)

    get_filename_component(_gccbin "${CMAKE_C_COMPILER}" DIRECTORY)
    add_custom_command(TARGET ${FW_NAME} POST_BUILD
        COMMAND "${_gccbin}/rx-elf-objcopy.exe" -O srec -I elf32-rx-be-ns
                "$<TARGET_FILE:${FW_NAME}>" "${FW_NAME}.mot"
        COMMAND "${_gccbin}/rx-elf-size.exe" --format=berkeley "$<TARGET_FILE:${FW_NAME}>"
        VERBATIM)

# ===========================================================================
else()  # CC-RX
# ===========================================================================
    # CC-RX のヘッダ/定義フラグ構文を再設定（C 情報モジュールが -I/-D に戻すため）
    set(CMAKE_INCLUDE_FLAG_C "-include=")
    set(CMAKE_C_DEFINE_FLAG  "-define=")

    add_library(fw_obj OBJECT ${_srcs})
    target_include_directories(fw_obj PRIVATE ${_incs})
    target_compile_definitions(fw_obj PRIVATE
        ${FW_DEFINES} MBEDTLS_CONFIG_FILE=<${MBEDTLS_CFG}>)

    set(_abs "${CMAKE_CURRENT_BINARY_DIR}/${FW_NAME}.abs")
    set(_mot "${CMAKE_CURRENT_BINARY_DIR}/${FW_NAME}.mot")
    set(_rtlib "${CMAKE_CURRENT_BINARY_DIR}/${FW_NAME}.lib")
    set(_port_obj "${CMAKE_CURRENT_BINARY_DIR}/port_asm.obj")
    set(_port_src "${REPO_ROOT}/Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port_asm.src")

    # アセンブラ用 subcommand（-include= が多くコマンドライン長制限に掛かるため）
    set(_asm_sub "${CMAKE_CURRENT_BINARY_DIR}/asrx.sub")
    set(_asm_content "-isa=rxv2\n-fpu\n-utf8\n-goptimize\n-nologo\n")
    foreach(i ${_incs})
        string(APPEND _asm_content "-include=${i}\n")
    endforeach()
    file(WRITE "${_asm_sub}" "${_asm_content}")

    # 1) アセンブル(port_asm.src → .obj)
    add_custom_command(OUTPUT "${_port_obj}"
        COMMAND "${RX_ASRX}" "-subcommand=${_asm_sub}" "-output=${_port_obj}" "${_port_src}"
        DEPENDS "${_port_src}" "${_asm_sub}" VERBATIM
        COMMENT "asrx port_asm.src")

    # 2) ランタイムライブラリ生成(lbgrx)
    #    CC-RX ツール(asrx/lbgrx/rlink)は CWD 上で同名の一時ファイルを使うため
    #    並行実行すると "Cannot open internal file" で衝突する。asrx の後に直列化する。
    add_custom_command(OUTPUT "${_rtlib}"
        COMMAND "${RX_LBGRX}" -isa=rxv2 -fpu -branch=32 -lang=c99
                -head=runtime,ctype,math,mathf,stdarg,stdio,stdlib,string,new,fenv,inttypes,wchar,wctype
                "-output=${_rtlib}" -goptimize -nologo
        DEPENDS "${_port_obj}"
        VERBATIM COMMENT "lbgrx runtime library")

    # 3) リンク用 subcommand を生成（オブジェクト列挙 + 固定オプション）
    #    ccrx_link_options.sub は -form/-start/-rom/-cpu 等のセクション配置を持つ
    #    純粋な rlink オプション断片（コメント無し。rlink がそのまま解釈する）。
    file(READ "${REPO_ROOT}/cmake/ccrx_link_options.sub" _opts)
    set(_link_sub "${CMAKE_CURRENT_BINARY_DIR}/Linker.sub")
    file(GENERATE OUTPUT "${_link_sub}" CONTENT
"-input=$<JOIN:$<TARGET_OBJECTS:fw_obj>,
-input=>
-input=${_port_obj}
-library=${_rtlib}
-output=${_abs}
${_opts}")

    # 4) リンク(rlink → .abs)
    #    オブジェクトの再コンパイルで確実に再リンクされるよう、TARGET_OBJECTS を
    #    依存に含める（fw_obj ターゲット依存だけでは個別オブジェクト変更を追えない）。
    add_custom_command(OUTPUT "${_abs}"
        COMMAND "${RX_RLINK}" "-subcommand=${_link_sub}"
        DEPENDS fw_obj $<TARGET_OBJECTS:fw_obj> "${_port_obj}" "${_rtlib}" "${_link_sub}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}" VERBATIM
        COMMENT "rlink -> ${FW_NAME}.abs")

    # 5) 変換(.abs → .mot)。rlink は -input をコマンドラインで受け付けないので
    #    こちらも subcommand 経由で渡す。
    set(_conv_sub "${CMAKE_CURRENT_BINARY_DIR}/Converter.sub")
    file(WRITE "${_conv_sub}"
        "-input=${_abs}\n-form=stype\n-output=${_mot}\n-byte_count=10\n-nologo\n")
    add_custom_command(OUTPUT "${_mot}"
        COMMAND "${RX_RLINK}" "-subcommand=${_conv_sub}"
        DEPENDS "${_abs}" "${_conv_sub}" VERBATIM
        COMMENT "rlink convert -> ${FW_NAME}.mot")

    add_custom_target(${FW_NAME} ALL DEPENDS "${_mot}")
endif()
