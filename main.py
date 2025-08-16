from astrbot.api.all import *
import aiohttp
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 常量配置
API_BASE_URL = "https://v2.xxapi.cn/api"
USER_AGENT = "xiaoxiaoapi/1.0.0 (https://xxapi.cn)"
COMMON_HEADERS = {"User-Agent": USER_AGENT}


@register("astrbot_websitetool", "wxgl",
          "集成网站测试工具，支持连通性测试、速度测试、域名查询、端口扫描和截图。使用/sitehelp查看帮助", "1.0")
class SiteToolsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))

    async def safe_fetch_json(self, url: str) -> dict:
        """安全获取JSON数据"""
        try:
            async with self.session.get(url, headers=COMMON_HEADERS) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API请求失败: {str(e)}")
            return {"code": 500, "msg": "服务暂时不可用"}
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            return {"code": 500, "msg": "内部服务器错误"}

    def parse_command_args(self, event: AstrMessageEvent, min_args: int = 1) -> list:
        """解析命令参数"""
        # 提取所有文本消息内容
        text_parts = [
            component.text.strip()
            for component in event.get_messages()
            if isinstance(component, Plain)  # 只处理Plain类型数据
        ]

        if not text_parts:
            return []

        full_text = "".join(text_parts)
        parts = full_text.split(maxsplit=1)

        if len(parts) < min_args + 1:
            return []

        return parts[1].split()  # 返回参数列表

    async def send_api_result(
            self,
            event: AstrMessageEvent,
            endpoint: str,
            params: dict,
            success_handler: callable
    ) -> MessageEventResult:
        """统一处理API请求和响应"""
        url = f"{API_BASE_URL}/{endpoint}"
        url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        logger.info(f"请求API: {url}")

        data = await self.safe_fetch_json(url)
        if data.get("code") == 200:
            return success_handler(data)
        else:
            return event.plain_result(f"\n错误：{data.get('msg', '未知错误')}")

    @command("sitehelp")
    async def show_help(self, event: AstrMessageEvent) -> MessageEventResult:
        """显示帮助信息"""
        help_text = """
站长工具使用帮助:

/sitehelp    - 显示帮助信息
/tcping <域名或IP地址> - TCP端口连通性测试
/ping <网址> - 测试网站连通性
/siteno <含http(s)的网址> - 测试网站延迟
/whois <域名> - 查询域名信息
/port <IP地址> - 端口扫描
/site <含http(s)的网址>  - 获取网站截图

示例:
/tcping bing.com 或 /tcping bing.com 443
/ping bing.com
/siteno https://www.bing.com
/whois bing.com
/port 8.8.8.8
/site https://www.bing.com"""
        return event.plain_result(help_text)

    @command("tcping")
    async def check_tcping(self, event: AstrMessageEvent) -> MessageEventResult:
        """TCP端口连通性测试"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("传入需要tcping的ip或者域名，不需要加http或https!\n示例: /tcping bing.com\n示例: /tcping bing.com 443")

        host = args[0]
        port = args[1] if len(args) > 1 else "80"  # 默认端口80

        try:
            port = int(port)
        except ValueError:
            return event.plain_result("端口号必须是数字!\n示例: /tcping bing.com 443")

        return await self.send_api_result(
            event,
            endpoint="tcping",
            params={"address": host, "port": port},
            success_handler=lambda data: event.plain_result(
                f"\n状态：{data['msg']}\n测试地址：{data['data']['address']}\n延迟：{data['data']['ping']}\n端口：{data['data']['port']}"
            )
        )

    @command("ping")
    async def check_ping(self, event: AstrMessageEvent) -> MessageEventResult:
        """检测网站连通性"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入要测试的域名!\n示例: /ping bing.com")

        return await self.send_api_result(
            event,
            endpoint="ping",
            params={"url": args[0]},
            success_handler=lambda data: event.plain_result(
                f"\n状态：{data['msg']}\n延迟：{data['data']['time']}\nIP：{data['data']['server']}"
            )
        )

    @command("siteno")
    async def check_latency(self, event: AstrMessageEvent) -> MessageEventResult:
        """检测网站延迟"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入要测试的网址，包含http(s)等！\n示例: /siteno https://www.bing.com")

        return await self.send_api_result(
            event,
            endpoint="speed",
            params={"url": args[0]},
            success_handler=lambda data: event.plain_result(
                f"\n状态：{data['msg']}\n延迟：{data['data']}ms"
            )
        )

    @command("whois")
    async def query_whois(self, event: AstrMessageEvent) -> MessageEventResult:
        """WHOIS查询"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入要查询的域名!\n示例: /whois bing.com")

        return await self.send_api_result(
            event,
            endpoint="whois",
            params={"domain": args[0]},
            success_handler=lambda data: event.plain_result(
                f"""\n域名：{data['data']['Domain Name']}
注册商：{data['data']['Sponsoring Registrar']}
注册人：{data['data']['Registrant']}
DNS：{', '.join(data['data']['DNS Serve'][:2])}
有效期：{data['data']['Registration Time']} 至 {data['data']['Expiration Time']}"""
            )
        )

    @command("port")
    async def scan_ports(self, event: AstrMessageEvent) -> MessageEventResult:
        """端口扫描"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入IP地址!\n示例: /port 8.8.8.8")

        return await self.send_api_result(
            event,
            endpoint="portscan",
            params={"address": args[0]},
            success_handler=lambda data: event.plain_result(
                self._format_port_scan(data['data'])
            )
        )

    def _format_port_scan(self, port_data: dict) -> str:
        """格式化端口扫描结果"""
        open_ports = [p for p, status in port_data.items() if status]
        closed_ports = [p for p, status in port_data.items() if not status]

        # 限制最多显示20个端口
        def truncate(ports):
            return ports[:20] + ["..."] if len(ports) > 20 else ports

        return f"""开放端口：{' | '.join(truncate(open_ports)) or '无'}
未开放端口：{' | '.join(truncate(closed_ports)) or '无'}"""

    @command("site")
    async def capture_site(self, event: AstrMessageEvent) -> MessageEventResult:
        """网站截图"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入网址,包含http(s)等!\n示例: /site https://www.bing.com")

        return await self.send_api_result(
            event,
            endpoint="screenshot",
            params={"url": args[0]},
            success_handler=lambda data: event.chain_result([
                Plain(f"截图成功：{data['msg']}\n"),
                Image.fromURL(data['data'])
            ])
        )
