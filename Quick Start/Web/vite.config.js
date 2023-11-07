/** @type {import('vite').UserConfig} */
export default {
    root: "src",
    envPrefix: "VEPHONE_",
    assetsInclude: ["lib/*"],
    server: {
        port: 8080 // 指定开发服务器端口。注意：如果端口已经被使用，Vite 会自动尝试下一个可用的端口，所以这可能不是开发服务器最终监听的实际端口。
    }
}