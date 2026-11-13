# 二进制来源与替代边界

精确 URL、字节数、SHA-256 均保存在 `locks/downloads.json`；源码仓库完整提交保存在 `default.xml`。下载地址可能失效，此时只接受与清单哈希一致的镜像文件。

| 来源 | 用途 | 是否必需下载 |
| --- | --- | --- |
| 小米官方 Global `OS3.0.301.0.WNCMIXM` OTA | houji 默认 vendor、common 的十五项覆盖、21 个固件 | 是 |
| 小米官方国行 `OS2.0.200.13.VNCCNXM` OTA | common 默认 vendor、四个相机文件覆盖 | 是 |
| 小米官方国行 `OS3.0.0.2.WNCCNXM` OTA | 当前预编译内核及模块的原厂字节来源证据 | 可选：`download --include-reference-kernel`；实际构建使用下方已匹配字节的固定仓库 |
| `lolipuru/device_xiaomi_houji-kernel`，`c9911a5ba8c206f25cc0c4e8a8b30dcfc88a4dce` | 下载预编译内核、模块和源代码头文件 | Repo 同步；按 `locks/kernel.json` 核验及清理 |
| PixelOS-AOSP GitLab 分发仓库 | GMS、Launcher、时钟、字体、声音、主题组件 | Repo / LFS 同步 |
| `tardyp/rs-bp` 固定提交 | AOSP Rust 缺失的 LFS fixture | 是，文件哈希必须与 AOSP 指针相同 |

745 个非空内核/模块/DTB 文件已匹配签名验证过的第三份官方包；两份空元数据保留，996 个源代码头文件按上游提交固定。本仓库按清单核对上游仓库字节，因此最小构建不必重新提取第三份 OTA。它没有声称能够从 Xiaomi 公布的内核源代码重新编译相同内核。

官方包原始来源：

- https://bn.d.miui.com/OS3.0.301.0.WNCMIXM/houji_global-ota_full-OS3.0.301.0.WNCMIXM-user-16.0-905b3920ab.zip
- https://bn.d.miui.com/OS2.0.200.13.VNCCNXM/houji-ota_full-OS2.0.200.13.VNCCNXM-user-15.0-020d8aabc8.zip
- 第三份包的精确地址以 `locks/downloads.json` 为准。

PixelOS 项目分发来源：

- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_gms-17
- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_launcher
- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_clocks
- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_gsans
- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_sounds
- https://gitlab.com/PixelOS-AOSP/proprietary_vendor_pixel_themepicker

这些仓库是 PixelOS 项目官方分发来源；不表示其中每个 Google 二进制已与 Google 官方镜像独立匹配。Xiaomi 设备适配和预编译内核仓库来自 lolipuru，并非 PixelOS 官方设备支持声明。

## 设备恢复包

KernelSU 来自项目官方 v3.3.1，已修补的 init_boot 和 Manager 与 ROM 一起保存在私有恢复包。成功用于通信修复的 `modemfirmware_a` 来自同一部手机；其精确原厂版本尚未认证。不能把最新版官方 `MODEM-FW.bin` 视为等价字节。

`modemst1/2`、`fsg`、`fsc`、`persist` 保存本机持久状态或校准相关数据，不是构建输入。现有采集属于故障现场备份。公共官方包里的同名通用镜像无法还原本机原有内容；不应跨设备复制这些备份。
