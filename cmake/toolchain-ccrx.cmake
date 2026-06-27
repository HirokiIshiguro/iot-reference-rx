# Renesas CC-RX (v3.07.00) 用 CMake ツールチェインファイル。
# CC-RX は CMake が自動認識できないコンパイラなので、コンパイラを強制し、
# CC-RX 独自のオプション構文でコンパイル規則を定義する。
# リンク(rlink)/アセンブル(asrx)/ライブラリ生成(lbgrx)は CMakeLists 側の
# カスタムコマンドで駆動する。
#
#   -DRX_CCRX_ROOT=<...> でツールチェインのルートを上書き可能。

set(CMAKE_SYSTEM_NAME      Generic)
set(CMAKE_SYSTEM_PROCESSOR rx)

if(NOT DEFINED RX_CCRX_ROOT)
    set(RX_CCRX_ROOT "C:/Program Files (x86)/Renesas/RX/3_7_0")
endif()
set(RX_CCRX_BIN "${RX_CCRX_ROOT}/bin")

set(CMAKE_C_COMPILER "${RX_CCRX_BIN}/ccrx.exe")
# asrx / lbgrx / rlink は CMakeLists から参照する
set(RX_ASRX  "${RX_CCRX_BIN}/asrx.exe"  CACHE FILEPATH "")
set(RX_LBGRX "${RX_CCRX_BIN}/lbgrx.exe" CACHE FILEPATH "")
set(RX_RLINK "${RX_CCRX_BIN}/rlink.exe" CACHE FILEPATH "")

# CC-RX の ABI 検査は通らないので強制
set(CMAKE_C_COMPILER_ID_RUN TRUE)
set(CMAKE_C_COMPILER_FORCED TRUE)
set(CMAKE_C_COMPILER_WORKS  TRUE)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_C_OUTPUT_EXTENSION ".obj")

# ヘッダ検索は "-include="（CMakeLists 側で再設定する: C 情報モジュールが -I に戻すため）
set(CMAKE_INCLUDE_FLAG_C "-include=")

# 共通コンパイルフラグ（e2 studio CC-RX プロジェクトと一致）
set(CMAKE_C_FLAGS_INIT "-isa=rxv2 -fpu -branch=32 -lang=c99 -utf8 -nomessage -debug -outcode=utf8 -goptimize -nologo")

# コンパイル規則: ccrx <flags> <defines> <includes> -output=obj=<OBJECT> <src>
set(CMAKE_C_COMPILE_OBJECT
    "<CMAKE_C_COMPILER> <FLAGS> <DEFINES> <INCLUDES> -output=obj=<OBJECT> <SOURCE>")
