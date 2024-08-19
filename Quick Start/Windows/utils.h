#pragma once
#include <string>
#include <vector>


// �ַ����ָ�
bool splitString(const std::string& src, const std::string& delim, std::vector<std::string>& segs);
bool splitString(const std::wstring& src, const std::wstring& delim, std::vector<std::wstring>& segs);

// ���ַ���
bool isWhiteSpace(const char c);
bool isWhiteSpace(const wchar_t c);

// ��Сдת��
std::string toLower(const std::string& s);
std::wstring toLower(const std::wstring& s);
std::string toUpper(const std::string& s);
std::wstring toUpper(const std::wstring& s);

// �ַ�ת��
std::string gbkToUtf8(const std::string& gbk_str);
std::string utf8ToGbk(const std::string& utf8_str);
std::string unicodeToUtf8(const std::wstring& uni_str);
wchar_t* AnsiToUnicode(const char* szStr);
std::wstring stringToWstring(const std::string& str);

// ʮ�����ƹ���
std::string toHex(const std::string& s);
std::string fromHex(const std::string& h);

// ���а����
void setClipboardContent(std::string text);
std::string getClipboardContent();

// ��ȡ��ǰʱ���
int64_t getCurrentTimeMs();

std::string GetPathAppend(const std::string& path, const std::string& more);

// ����������������Ϣ
template<typename... Args>
static void vePrint(const std::string& str, const Args... args) {
    std::string output = fmt::format(str + "\n", args...);
    ::OutputDebugStringA(output.c_str());
}