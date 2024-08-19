#include "pch.h"
#include "utils.h"
#include "strsafe.h"
#include <Shlwapi.h>
#pragma comment(lib, "Shlwapi.lib")

template<typename T>
static bool splitstringInternal(const std::basic_string<T, std::char_traits<T>, std::allocator<T>>& src, \
    const std::basic_string<T, std::char_traits<T>, std::allocator<T>>& delim, \
    std::vector<std::basic_string<T, std::char_traits<T>, std::allocator<T>>>& segs);


bool splitString(const std::string& src, const std::string& delim, std::vector<std::string>& segs) {
    return splitstringInternal<char>(src, delim, segs);
}

bool splitString(const std::wstring& src, const std::wstring& delim, std::vector<std::wstring>& segs) {
    return splitstringInternal<wchar_t>(src, delim, segs);
}

bool isWhiteSpace(const char c) {
    return c == ' ' || c == '\n' || c == '\r' || c == '\f' || c == '\v';
}

bool isWhiteSpace(const wchar_t c) {
    return c == L' ' || c == L'\n' || c == L'\r' || c == L'\f' || c == L'\v';
}

std::string toLower(const std::string& s) {
    std::string r = s;
    std::transform(r.begin(), r.end(), r.begin(),
        [](char c) {
            return std::tolower(c);
        }
    );
    return r;
}

std::wstring toLower(const std::wstring& s) {
    std::wstring r = s;
    std::transform(r.begin(), r.end(), r.begin(),
        [](wchar_t c) {
            return std::tolower(c);
        }
    );
    return r;
}

std::string toUpper(const std::string& s) {
    std::string r = s;
    std::transform(r.begin(), r.end(), r.begin(),
        [](char c) {
            return std::toupper(c);
        }
    );
    return r;
}

std::wstring toUpper(const std::wstring& s) {
    std::wstring r = s;
    std::transform(r.begin(), r.end(), r.begin(),
        [](wchar_t c) {
            return std::toupper(c);
        }
    );
    return r;
}

std::string unicodeToUtf8(const std::wstring& wstr) {
    std::string str;

    int nLen = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), (int)wstr.size(), NULL, 0, NULL, NULL);
    str.resize((size_t)nLen);

    WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), (int)wstr.size(), (LPSTR)str.c_str(), nLen, NULL, NULL);

    return str;
}

std::string toHex(const std::string& s) {
    if (s.empty()) {
        return "";
    }

    // 
    static const char hex2digit[] = "0123456789ABCDEF";
    std::string tmp(s.length() * 2, '\0');
    char* ptr_h = &tmp[0];
    char* ptr_s = const_cast<char*>(&s[0]);
    char* ptr_s_end = ptr_s + s.length();
    while (ptr_s < ptr_s_end) {
        *ptr_h++ = hex2digit[(*ptr_s >> 4) & 0x0F];
        *ptr_h++ = hex2digit[*ptr_s & 0x0F];
        ++ptr_s;
    }

    return tmp;
}

std::string fromHex(const std::string& h) {
    if (h.empty()) {
        return "";
    }
    if (h.length() % 2 > 0) {
        return "";
    }

    // 
    auto func_check = [](const char c) -> bool {
        return !(c < '0' || c >'F' || (c > '9' && c < 'A'));
    };
    auto func_calc_c = [](const char c) -> unsigned char {
        if (c >= '0' && c <= '9') {
            return static_cast<unsigned char>(c - '0');
        }
        if (c >= 'A' && c <= 'F') {
            return static_cast<unsigned char>(c - 'A') + 0x0A;
        }
        return 0;
    };
    auto func_calc = [func_calc_c](const char hi, const char lo) -> const char {
        unsigned char c = 0;
        c = func_calc_c(hi) << 4;
        c += func_calc_c(lo);
        return *reinterpret_cast<char*>(&c);
    };

    // 
    std::string tmp(h.length() / 2, '\0');
    char* ptr_s = &tmp[0];
    char* ptr_h = const_cast<char*>(&h[0]);
    char* ptr_h_end = ptr_h + h.length();
    while (ptr_h < ptr_h_end) {
        char high = *ptr_h++;
        char low = *ptr_h++;
        if (!func_check(high) || !func_check(low)) {
            return "";
        }
        *ptr_s++ = func_calc(high, low);
    }

    return tmp;
}

template<typename T>
bool splitstringInternal(const std::basic_string<T, std::char_traits<T>, std::allocator<T>>& src, \
    const std::basic_string<T, std::char_traits<T>, std::allocator<T>>& delim, \
    std::vector<std::basic_string<T, std::char_traits<T>, std::allocator<T>>>& segs) {
    if (src.empty())
        return true;
    if (delim.empty()) {
        segs.push_back(src);
        return true;
    }

    // 未找到分隔符
    size_t pos = src.find(delim);
    if (pos == std::basic_string<T, std::char_traits<T>, std::allocator<T>>::npos) {
        segs.push_back(src);
        return true;
    }

    // 寻找分段
    size_t last_pos = 0;
    do {
        if (pos - last_pos > 0) {
            std::basic_string<T, std::char_traits<T>, std::allocator<T>> seg = src.substr(last_pos, pos - last_pos);
            segs.push_back(seg);
        }
        last_pos = pos + 1;
        if (last_pos + 1 > src.length())
            break;
        pos = src.find(delim, last_pos);
    } while (pos != std::basic_string<T, std::char_traits<T>, std::allocator<T>>::npos);

    // 剩余部分处理
    if (last_pos < src.length()) {
        std::basic_string<T, std::char_traits<T>, std::allocator<T>> seg = src.substr(last_pos);
        segs.push_back(seg);
    }

    return true;
}

std::wstring stringToWstring(const std::string& str) {
    std::wstring result;
    int len = MultiByteToWideChar(CP_ACP, 0, str.c_str(), (int)str.size(), NULL, 0);
    WCHAR* buffer = new WCHAR[(size_t)len + 1];
    if (!buffer) {
        return std::wstring();
    }
    MultiByteToWideChar(CP_ACP, 0, str.c_str(), (int)str.size(), buffer, len);
    buffer[len] = '\0';
    result.append(buffer);
    delete[] buffer;
    return result;
}

wchar_t* AnsiToUnicode(const char* szStr) {
    int nLen = MultiByteToWideChar(CP_ACP, MB_PRECOMPOSED, szStr, -1, NULL, 0);
    if (nLen == 0) {
        return NULL;
    }
    wchar_t* pResult = new wchar_t[nLen];
    MultiByteToWideChar(CP_ACP, MB_PRECOMPOSED, szStr, -1, pResult, nLen);
    return pResult;
}

int64_t getCurrentTimeMs() {
    int64_t ts = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    return ts;
}

std::string getClipboardContent() {
    std::string res;

    EmptyClipboard();
    if (!OpenClipboard(nullptr)) {
        return res;
    }
    HANDLE h_data = GetClipboardData(CF_TEXT);
    if (h_data == NULL) {
        return res;
    }

    do {
        char* tmp_text = static_cast<char*>(GlobalLock(h_data));
        if (!tmp_text) {
            break;
        }

        res = tmp_text;
        GlobalUnlock(h_data);
    } while (false);

    if (!CloseClipboard()) {
        return res;
    }
    return res;
}

void setClipboardContent(std::string text) {
    if (OpenClipboard(NULL)) {
        EmptyClipboard();
        HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, text.size() + 1);
        if (hMem) {
            char* pMem = (char*)GlobalLock(hMem);
            strcpy_s(pMem, text.size() + 1, text.c_str());
            GlobalUnlock(hMem);

            SetClipboardData(CF_TEXT, hMem);
        }
        CloseClipboard();
    }
}

std::string GetPathAppend(const std::string& path, const std::string& more) {
    CHAR strTemp[MAX_PATH] = { 0 };
    HRESULT hr = StringCbCopyA(strTemp, MAX_PATH * sizeof(CHAR), path.c_str());
    if (FAILED(hr)) {
        return std::string();
    }
    bool res = PathAppendA(strTemp, more.c_str());
    if (!res) {
        return std::string();
    }
    return strTemp;
}