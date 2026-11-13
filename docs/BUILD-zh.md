# 构建步骤

## 环境与目录

建议 Linux x86-64、Python 3.11+、Git、Repo、Git LFS、Podman。完整源码和编译产物仍然占用数百 GB；小型仓库只减少长期归档内容。Repo 运行时固定为 v2.72 对应提交，launcher 可由发行版安装。宿主必须能执行 `repo`、`git-lfs`，且可访问清单中的上游服务。

将本仓库克隆到独立路径；下面的 `WORK` 由你选择，必须位于仓库外。首次构建使用空目录。命令均在本仓库根目录执行：

```bash
export WORK="$HOME/build/houji-working-20261112"
podman build --build-arg BASE_IMAGE=public.ecr.aws/ubuntu/ubuntu:24.04 \
  --build-arg UBUNTU_ARCHIVE=http://security.ubuntu.com/ubuntu/ \
  -t localhost/pixelos-build:ubuntu24.04 -f environment/Containerfile environment
python3 scripts/reproduce.py --work "$WORK" init
python3 scripts/reproduce.py --work "$WORK" --jobs 4 sync
python3 scripts/reproduce.py --work "$WORK" download
python3 scripts/reproduce.py --work "$WORK" lfs
python3 scripts/reproduce.py --work "$WORK" configure
python3 scripts/reproduce.py --work "$WORK" extract
python3 scripts/reproduce.py --work "$WORK" stage
python3 scripts/reproduce.py --work "$WORK" generate
python3 scripts/reproduce.py --work "$WORK" --jobs 8 verify
python3 scripts/reproduce.py --work "$WORK" --jobs 12 build
```

可用 `--image NAME_OR_ID` 指定本地容器镜像，不依赖原机器容器 ID；`--source PATH` 可指定源码目录，例如对现有成功构建做只读核验。原构建软件包清单保存在 `environment/packages-reference.tsv`，它是环境记录；Containerfile 当前的 apt 包版本不固定，不能据此声称完整工具链环境逐字节复现。

## 各步骤作用

1. `init` 从本仓库当前提交建立 Repo 清单，固定 1,236 个项目；`sync` 下载源代码，先跳过 LFS smudge。
2. `download` 下载两份必需的 Xiaomi OTA 和缺失的 Rust LFS fixture。已有文件必须通过大小及 SHA-256 校验；不接受“相似版本”。可手动下载并按 `locks/downloads.json` 的文件名放入 `$WORK/downloads`，再运行该命令校验。
3. `lfs` 从固定的 PixelOS GMS 仓库取得八个 LFS 对象，并恢复 AOSP Rust fixture 缺失的本地 attributes 映射。九个文件均核对完整哈希。
4. `configure` 验证五个补丁目标仓库的原始提交，预检七个补丁，核对最终十个文件；检查全部内核/头文件后，仅删除列明的八个旧模块。若存在未记录的修改会停止。
5. `extract` 校验官方包，再调用固定源码树的 OTA 提取工具；每个分区镜像核验大小及 SHA-256，再用容器内的 EROFS/ext4 工具提取文件。部分失败的 dump 目录会保留，应检查失败原因并移走该目录后重跑。
6. `stage` 按显式来源映射生成 3,195 个 vendor 原始文件、21 个固件文件和一个查找别名。国行/Global 混合选择、四个相机覆盖及十五个 common 覆盖已写入清单。
7. `generate` 使用上游提取规则和本地修正生成 vendor，包含原流程中的 176 项处理；按原成功构建保存的 3,224 个最终文件/链接逐项核验。
8. `verify` 检查所有项目 HEAD、未记录改动、补丁最终字节、内核、LFS 和 vendor。`build` 在编译前后都运行核验，容器关闭网络且不挂载手机设备；使用原基准的固定构建日期和编号。

`configure` 可对已经正确配置的源码重复运行。`extract`、`stage`、`generate` 拒绝覆盖已有输出，避免误删或掩盖半成品。不要在正在编译或同步的源码树运行配置步骤。

## 产物与边界

产物位于 `$WORK/source/out/target/product/houji/`。新构建仍须检查 OTA 内容、签名及设备兼容性后再考虑安装。构建时间常量不是 Android 安全补丁状态的证明。

保留本仓库即可在线重建输入，前提是上游固定提交、LFS 对象及官方包仍可下载。完全离线重建需要另行镜像全部上游内容和环境。此整理工作未重跑完整 Android 编译，也未刷写手机。
