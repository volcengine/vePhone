#pragma once

#ifdef NATIVESDK_EXPORTS
#define NATIVESDK_API __declspec(dllexport)
#else
#define NATIVESDK_API __declspec(dllimport)
#endif // NATIVESDK_EXPORTS

