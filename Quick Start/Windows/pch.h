#ifndef PCH_H
#define PCH_H

// 添加要在此处预编译的标头
// windows
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <WinInet.h>
#include <winnt.h>
#include <iphlpapi.h>

#include <commdlg.h>
#include <d2d1.h>
#include <dwmapi.h>
#include <dwrite.h>
#include <hidusage.h>
#include <imm.h>
#include <shellapi.h>
#include <ShellScalingApi.h>
#include <Shlobj.h>
#include <ShObjIdl.h>
#include <ShObjIdl_core.h>
#include <rpc.h>
#include <wincodec.h>
#include <winrt/base.h>
#include <Xinput.h>

// c++ 
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <codecvt>
#include <locale>
#include <fmt/format.h>

// 3rd party

// 
#include "Resource.h"
#include "utils.h"

#endif //PCH_H
