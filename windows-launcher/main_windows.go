//go:build windows

package main

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	mbOK          = 0x00000000
	mbYesNo       = 0x00000004
	mbIconInfo    = 0x00000040
	mbIconWarning = 0x00000030
	idYes         = 6
)

var (
	user32      = syscall.NewLazyDLL("user32.dll")
	messageBoxW = user32.NewProc("MessageBoxW")
)

func messageBox(title, text string, flags uintptr) int {
	titlePtr, _ := syscall.UTF16PtrFromString(title)
	textPtr, _ := syscall.UTF16PtrFromString(text)
	result, _, _ := messageBoxW.Call(0, uintptr(unsafe.Pointer(textPtr)), uintptr(unsafe.Pointer(titlePtr)), flags)
	return int(result)
}

func projectRoot() (string, error) {
	executable, err := os.Executable()
	if err != nil {
		return "", err
	}
	candidates := []string{
		filepath.Dir(executable),
		filepath.Dir(filepath.Dir(executable)),
		filepath.Dir(filepath.Dir(filepath.Dir(executable))),
	}
	if working, err := os.Getwd(); err == nil {
		candidates = append(candidates, working)
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(filepath.Join(candidate, "compose.yaml")); err == nil {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("找不到 compose.yaml。请把 EXE 放回 ForgeGuard 完整项目目录")
}

func logFile(root string) *os.File {
	_ = os.MkdirAll(filepath.Join(root, "runtime-data"), 0o755)
	file, err := os.OpenFile(filepath.Join(root, "runtime-data", "windows-launcher.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return nil
	}
	_, _ = fmt.Fprintf(file, "\n[%s] desktop launcher started\n", time.Now().Format(time.RFC3339))
	return file
}

func commandExists(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func serviceHealthy() bool {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	response, err := client.Get("http://127.0.0.1:8000/api/v1/health")
	if err != nil {
		return false
	}
	defer response.Body.Close()
	return response.StatusCode >= 200 && response.StatusCode < 300
}

func waitForService(timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if serviceHealthy() {
			return true
		}
		time.Sleep(900 * time.Millisecond)
	}
	return false
}

func runDocker(root string, log *os.File) error {
	cmd := exec.Command("docker", "compose", "-f", filepath.Join(root, "compose.yaml"), "up", "-d", "--build", "api")
	cmd.Dir = root
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	return cmd.Run()
}

func stopDocker(root string, log *os.File) error {
	cmd := exec.Command("docker", "compose", "-f", filepath.Join(root, "compose.yaml"), "down")
	cmd.Dir = root
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	return cmd.Run()
}

func readPointer(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(strings.TrimPrefix(string(data), "\ufeff"))
}

func appendUnique(values []string, value string) []string {
	value = strings.TrimSpace(value)
	if value == "" {
		return values
	}
	cleaned := filepath.Clean(value)
	for _, existing := range values {
		if strings.EqualFold(filepath.Clean(existing), cleaned) {
			return values
		}
	}
	return append(values, cleaned)
}

func nativeVenvDirs(root string) []string {
	values := []string{}
	values = appendUnique(values, os.Getenv("FORGEGUARD_VENV_DIR"))

	runtimeHome := strings.TrimSpace(os.Getenv("FORGEGUARD_RUNTIME_HOME"))
	if runtimeHome == "" {
		if local := os.Getenv("LOCALAPPDATA"); local != "" {
			runtimeHome = filepath.Join(local, "ForgeGuardNexus")
		}
	}
	if runtimeHome != "" {
		values = appendUnique(values, readPointer(filepath.Join(runtimeHome, "venv-path.txt")))
		values = appendUnique(values, filepath.Join(runtimeHome, "venv"))
	}

	// The project pointer is recreated in every extracted package and supports a
	// custom persistent path without requiring a permanent environment variable.
	values = appendUnique(values, readPointer(filepath.Join(root, ".venv-path.txt")))
	// Compatibility with releases before the persistent runtime manager.
	values = appendUnique(values, filepath.Join(root, ".venv"))
	return values
}

func nativePython(root string) string {
	for _, venv := range nativeVenvDirs(root) {
		candidate := filepath.Join(venv, "Scripts", "python.exe")
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return ""
}

func nativeEnvironmentReady(root, python string, log *os.File) bool {
	venvDir := filepath.Dir(filepath.Dir(python))
	helper := filepath.Join(root, "scripts", "native_env.py")
	cmd := exec.Command(python, helper, "status", "--venv", venvDir, "--repair", "--quiet")
	cmd.Dir = root
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	return cmd.Run() == nil
}

func startNative(root, python string, log *os.File) error {
	cmd := exec.Command(python, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000")
	cmd.Dir = root
	cmd.Env = append(
		os.Environ(),
		"PYTHONPATH="+filepath.Join(root, "backend")+string(os.PathListSeparator)+filepath.Join(root, "edge-node"),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
	)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x00000008 | 0x08000000}
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(root, "runtime-data", "forgeguard-native.pid"), []byte(strconv.Itoa(cmd.Process.Pid)), 0o644)
}

func stopNative(root string, log *os.File) error {
	data, err := os.ReadFile(filepath.Join(root, "runtime-data", "forgeguard-native.pid"))
	if err != nil {
		return fmt.Errorf("没有找到原生服务 PID 文件")
	}
	pid := strings.TrimSpace(string(data))
	cmd := exec.Command("taskkill", "/PID", pid, "/T", "/F")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	err = cmd.Run()
	_ = os.Remove(filepath.Join(root, "runtime-data", "forgeguard-native.pid"))
	return err
}

func runInstaller(root string, log *os.File) error {
	// Use a dedicated console-subsystem helper. The previous implementation
	// redirected PowerShell stdout/stderr only to windows-launcher.log, which
	// created a blank terminal after the user confirmed installation.
	setup := filepath.Join(root, "ForgeGuard-Native-Setup.exe")
	if _, err := os.Stat(setup); err == nil {
		cmd := exec.Command(setup, root)
		cmd.Dir = root
		cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000010} // CREATE_NEW_CONSOLE
		return cmd.Run()
	}

	// Development/source-tree fallback when the helper has not been built yet.
	script := filepath.Join(root, "deploy", "windows", "install-native.ps1")
	commandLine := fmt.Sprintf(
		`start "ForgeGuard Nexus 环境安装" /WAIT powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%s"`,
		strings.ReplaceAll(script, `"`, `""`),
	)
	cmd := exec.Command("cmd.exe", "/D", "/S", "/C", commandLine)
	cmd.Dir = root
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if log != nil {
		_, _ = fmt.Fprintln(log, "ForgeGuard-Native-Setup.exe missing; using visible PowerShell fallback")
	}
	return cmd.Run()
}

func desktopEngineCandidates() []string {
	values := []string{}
	if local := os.Getenv("LOCALAPPDATA"); local != "" {
		values = append(values,
			filepath.Join(local, "Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join(local, "Google", "Chrome", "Application", "chrome.exe"),
		)
	}
	if pf := os.Getenv("ProgramFiles"); pf != "" {
		values = append(values,
			filepath.Join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join(pf, "Google", "Chrome", "Application", "chrome.exe"),
		)
	}
	if pf86 := os.Getenv("ProgramFiles(x86)"); pf86 != "" {
		values = append(values,
			filepath.Join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
		)
	}
	if edge, err := exec.LookPath("msedge.exe"); err == nil {
		values = append([]string{edge}, values...)
	}
	if chrome, err := exec.LookPath("chrome.exe"); err == nil {
		values = append([]string{chrome}, values...)
	}
	return values
}

func findDesktopEngine() string {
	for _, candidate := range desktopEngineCandidates() {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return ""
}

func openDesktopWindow(root string, log *os.File) error {
	engine := findDesktopEngine()
	if engine == "" {
		return fmt.Errorf("未找到 Microsoft Edge 或 Google Chrome 桌面运行时")
	}
	profile := filepath.Join(root, "runtime-data", "desktop-profile")
	_ = os.MkdirAll(profile, 0o755)
	args := []string{
		"--app=http://127.0.0.1:8000/?desktop=1",
		"--start-maximized",
		"--no-first-run",
		"--disable-session-crashed-bubble",
		"--disable-features=msEdgeSidebarV2,msEdgeShoppingAssistant",
		"--user-data-dir=" + profile,
	}
	cmd := exec.Command(engine, args...)
	cmd.Dir = root
	if log != nil {
		cmd.Stdout = log
		cmd.Stderr = log
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	return nil
}

func openWebBrowser() {
	_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", "http://127.0.0.1:8000").Start()
}

func ensureService(root string, log *os.File) error {
	if serviceHealthy() {
		return nil
	}
	if commandExists("docker") {
		if err := runDocker(root, log); err != nil {
			return fmt.Errorf("Docker 启动失败：%w", err)
		}
	} else if python := nativePython(root); python != "" && nativeEnvironmentReady(root, python, log) {
		if err := startNative(root, python, log); err != nil {
			return fmt.Errorf("原生服务启动失败：%w", err)
		}
	} else {
		answer := messageBox("ForgeGuard Nexus", "没有找到可复用的原生运行环境，或依赖版本需要同步。\n\n是否现在打开安装进度窗口？窗口会实时显示创建环境、下载依赖和模型校验过程。首次安装需要 Python 3.11/3.12 和网络连接。", mbYesNo|mbIconWarning)
		if answer != idYes {
			return fmt.Errorf("用户取消安装")
		}
		if err := runInstaller(root, log); err != nil {
			return fmt.Errorf("原生安装失败：%w", err)
		}
		python := nativePython(root)
		if python == "" || !nativeEnvironmentReady(root, python, log) {
			return fmt.Errorf("安装结束，但持久化运行环境未通过校验")
		}
		if err := startNative(root, python, log); err != nil {
			return fmt.Errorf("原生服务启动失败：%w", err)
		}
	}
	if !waitForService(4 * time.Minute) {
		return fmt.Errorf("服务在规定时间内没有通过健康检查")
	}
	return nil
}

func main() {
	root, err := projectRoot()
	if err != nil {
		messageBox("ForgeGuard Nexus", err.Error(), mbOK|mbIconWarning)
		return
	}
	log := logFile(root)
	if log != nil {
		defer log.Close()
	}

	base := strings.ToLower(filepath.Base(os.Args[0]))
	action := "desktop"
	if strings.Contains(base, "stop") {
		action = "stop"
	}
	if len(os.Args) > 1 {
		action = strings.ToLower(os.Args[1])
	}

	if action == "stop" {
		var stopErr error
		if commandExists("docker") {
			stopErr = stopDocker(root, log)
		} else {
			stopErr = stopNative(root, log)
		}
		if stopErr != nil {
			messageBox("ForgeGuard Nexus", "停止服务失败：\n"+stopErr.Error()+"\n\n详情见 runtime-data\\windows-launcher.log", mbOK|mbIconWarning)
			return
		}
		messageBox("ForgeGuard Nexus", "ForgeGuard 服务已停止。", mbOK|mbIconInfo)
		return
	}

	if err := ensureService(root, log); err != nil {
		if strings.Contains(err.Error(), "用户取消") {
			return
		}
		messageBox("ForgeGuard Nexus", err.Error()+"\n\n详情见 runtime-data\\windows-launcher.log", mbOK|mbIconWarning)
		return
	}

	if action == "web" {
		openWebBrowser()
		return
	}

	if err := openDesktopWindow(root, log); err != nil {
		messageBox("ForgeGuard Nexus", "无法打开独立软件窗口：\n"+err.Error()+"\n\n将改用默认浏览器。", mbOK|mbIconWarning)
		openWebBrowser()
	}
}
