# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile
# 保留注解，尤其是@Keep注解的保留
-keepattributes *Annotation*,InnerClasses,Signature,Exceptions
# QuickHttp库的Websocket能力没有在cp_core_demo中直接使用
# 所以对于onlineLite包而言，大概率会被因未被使用而被移除
# 造成自研埋点初始化失败
-keep class com.bytedance.http.**{*;}
-keep class com.volcengine.**{*;}

#保留枚举类不被混淆
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}