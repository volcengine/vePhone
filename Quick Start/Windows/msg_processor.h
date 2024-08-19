#pragma once
#include "pch.h"
#include "Resource.h"
#include <verender_cloudx.h>
#include "ve_qk_class.h"
#include "ve_qk_demo.h"


void ProcessWmInput(PhoneSession* session, RECT& validArea, HWND hWnd, UINT message, WPARAM wParam, LPARAM lparam);
void ProcessWmChar(PhoneSession* session, HWND hWnd, UINT message, WPARAM wParam, LPARAM lparam);
void ProcessWmKeyAction(PhoneSession* session, HWND hWnd, UINT message, WPARAM wParam, LPARAM lparam);
void ProcessWmCmd(PhoneSession* session, std::string& podId, QkSessionListener* listener, HINSTANCE instance, HWND hWnd, WPARAM wParam, LPARAM lParam);
INT_PTR CALLBACK getDialogContent(HWND, UINT, WPARAM, LPARAM);