# Xiaomi 14 · personal PixelOS 17 build recipe

为国行 Xiaomi 14（`houji` / `23127PN0CC`）保存的**小型构建仓库**。基准是用户于 2026-11-12 确认可运行的第 003 次个人构建。此仓库不是 PixelOS 官方设备发行版，也不包含可直接刷写的 ROM。

这里保存 1,236 个上游仓库的固定提交、七个本地补丁、可配置的构建脚本，以及下载、vendor、内核、LFS 校验清单。编译时联网取得上游源码和必要二进制；不再单独维护必要二进制包。

| 内容 | 获取方式 |
| --- | --- |
| PixelOS / AOSP / LineageOS 源码 | `default.xml` 固定提交，Repo 同步 |
| GMS、Pixel Launcher、字体、声音等 | 清单中的 PixelOS 官方 GitLab 分发仓库，固定提交；这不等同于逐项验证 Google 原厂来源 |
| Xiaomi vendor / 固件输入 | 两份固定版本官方 OTA，按 SHA-256 验证后提取 |
| 预编译内核、模块、DTB/DTBO | 固定版本 `lolipuru/device_xiaomi_houji-kernel`，逐项验证 747 个文件与 996 个头文件，移除八个旧模块；745 个非空二进制已匹配官方国行 OS3.0.0.2 |
| 本机恢复材料 | 单独的私有设备恢复包；不进入本仓库或 GitHub Release |

从 [构建步骤](docs/BUILD-zh.md) 开始。下载来源及精确版本见 [二进制来源](docs/SOURCES-zh.md)，验收范围见 [验证记录](docs/VALIDATION-zh.md)。

基准构建：`custom_houji-cp2a-userdebug`，`personal.8014d1536138`；原始 OTA 为 `PixelOS_houji-17.0-20261110-0322.zip`，SHA-256：

```
aa75a12d78836686b190c33c1842d260c687007e754c9c3cf5694f47a4528b5a
```

原始 OTA 含 Global OS3.0.301 的 21 个底层固件镜像；后装 KernelSU 和成功的 modemfirmware 修复不在 OTA 内。重新编译或安装 OTA **不会自动得到手机上完整的当前组合**。本仓库的构建脚本不连接或刷写手机。

这是开发签名、未强制 AVB 验证的个人实验构建，不能据此重新锁定 Bootloader。使用“最新”官方包会改变输入，应作为新版本重新验证。固定输入和构建时间尚未通过第二次独立完整构建证明 ZIP 逐字节一致。

原本地记录标签 `pixelos-17-houji-working-20261112` 位于旧清单仓库，提交为 `5e82685325a39f8540de37f1d5b77c9c816bf144`。本仓库使用新的、仅包含公开构建材料的 Git 历史；`working-20261112-kit-v1` 是整理后的复现材料标签。
