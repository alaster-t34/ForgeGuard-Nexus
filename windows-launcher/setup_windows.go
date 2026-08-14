//go:build windows

package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var (
	kernel32Setup      = syscall.NewLazyDLL("kernel32.dll")
	allocConsole       = kernel32Setup.NewProc("AllocConsole")
	getConsoleWindow   = kernel32Setup.NewProc("GetConsoleWindow")
	setConsoleTitleW   = kernel32Setup.NewProc("SetConsoleTitleW")
	setStdHandle       = kernel32Setup.NewProc("SetStdHandle")
	setConsoleCP       = kernel32Setup.NewProc("SetConsoleCP")
	setConsoleOutputCP = kernel32Setup.NewProc("SetConsoleOutputCP")
)

const (
	stdInputHandle  = ^uintptr(9)  // DWORD(-10)
	stdOutputHandle = ^uintptr(10) // DWORD(-11)
	stdErrorHandle  = ^uintptr(11) // DWORD(-12)
)

func attachVisibleConsole() {
	window, _, _ := getConsoleWindow.Call()
	if window == 0 {
		_, _, _ = allocConsole.Call()
	}
	_, _, _ = setConsoleCP.Call(65001)
	_, _, _ = setConsoleOutputCP.Call(65001)

	stdin, errIn := os.OpenFile("CONIN$", os.O_RDWR, 0)
	stdout, errOut := os.OpenFile("CONOUT$", os.O_WRONLY, 0)
	if errIn == nil {
		os.Stdin = stdin
		_, _, _ = setStdHandle.Call(stdInputHandle, stdin.Fd())
	}
	if errOut == nil {
		os.Stdout = stdout
		os.Stderr = stdout
		_, _, _ = setStdHandle.Call(stdOutputHandle, stdout.Fd())
		_, _, _ = setStdHandle.Call(stdErrorHandle, stdout.Fd())
	}

	title, _ := syscall.UTF16PtrFromString("ForgeGuard Nexus - 原生运行环境安装")
	_, _, _ = setConsoleTitleW.Call(uintptr(unsafe.Pointer(title)))
}

func setupRoot() (string, error) {
	if len(os.Args) > 1 {
		candidate, err := filepath.Abs(os.Args[1])
		if err == nil {
			if _, statErr := os.Stat(filepath.Join(candidate, "compose.yaml")); statErr == nil {
				return candidate, nil
			}
		}
	}

	executable, err := os.Executable()
	if err != nil {
		return "", err
	}
	candidates := []string{filepath.Dir(executable), filepath.Dir(filepath.Dir(executable))}
	if working, cwdErr := os.Getwd(); cwdErr == nil {
		candidates = append(candidates, working)
	}
	for _, candidate := range candidates {
		if _, statErr := os.Stat(filepath.Join(candidate, "compose.yaml")); statErr == nil {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("找不到 ForgeGuard 完整项目目录（缺少 compose.yaml）")
}

func pauseOnFailure() {
	fmt.Println()
	fmt.Println("按 Enter 键关闭此窗口。")
	_, _ = bufio.NewReader(os.Stdin).ReadString('\n')
}

func main() {
	attachVisibleConsole()

	root, err := setupRoot()
	if err != nil {
		fmt.Println("[错误]", err)
		pauseOnFailure()
		os.Exit(1)
	}

	_ = os.MkdirAll(filepath.Join(root, "runtime-data"), 0o755)
	logPath := filepath.Join(root, "runtime-data", "native-installer.log")
	logFile, logErr := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if logErr == nil {
		defer logFile.Close()
	}

	writer := io.Writer(os.Stdout)
	if logFile != nil {
		writer = io.MultiWriter(os.Stdout, logFile)
	}

	fmt.Fprintln(writer, strings.Repeat("=", 72))
	fmt.Fprintln(writer, "ForgeGuard Nexus 原生运行环境安装")
	fmt.Fprintln(writer, strings.Repeat("=", 72))
	fmt.Fprintln(writer, "检测到当前没有可复用环境，或依赖版本需要同步。")
	fmt.Fprintln(writer, "本窗口会实时显示创建虚拟环境、下载依赖和模型校验进度。")
	fmt.Fprintln(writer, "首次安装通常需要数分钟；请保持网络连接，不要关闭窗口。")
	fmt.Fprintln(writer, "项目目录：", root)
	fmt.Fprintln(writer, "日志文件：", logPath)
	fmt.Fprintln(writer)

	script := filepath.Join(root, "deploy", "windows", "install-native.ps1")
	cmd := exec.Command(
		"powershell.exe",
		"-NoLogo",
		"-NoProfile",
		"-ExecutionPolicy", "Bypass",
		"-File", script,
	)
	cmd.Dir = root
	cmd.Env = append(os.Environ(), "PYTHONUTF8=1", "PYTHONIOENCODING=utf-8")
	cmd.Stdin = os.Stdin
	cmd.Stdout = writer
	cmd.Stderr = writer

	start := time.Now()
	if err := cmd.Run(); err != nil {
		fmt.Fprintln(writer)
		fmt.Fprintln(writer, "[安装失败] 原生运行环境未能完成同步。")
		fmt.Fprintln(writer, "原因：", err)
		fmt.Fprintln(writer, "请查看日志：", logPath)
		pauseOnFailure()
		os.Exit(1)
	}

	fmt.Fprintln(writer)
	fmt.Fprintln(writer, "[安装完成] ForgeGuard 原生运行环境已就绪。")
	fmt.Fprintf(writer, "总耗时：%s\n", time.Since(start).Round(time.Second))
	fmt.Fprintln(writer, "软件将在 2 秒后继续启动。")
	time.Sleep(2 * time.Second)
}
