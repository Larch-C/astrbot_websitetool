from astrbot.api.star import Context, Star, register
from astrbot.api.platform import AstrMessageEvent
from astrbot.api.message.message_event_result import MessageEventResult, MessageChain
from astrbot.api.message_components import Plain, Image
from astrbot.api.star.filter.event_message_type import EventMessageTypeFilter, EventMessageType
import aiohttp
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 常量配置
API_BASE_URL = "https://v2.xxapi.cn/api"
USER_AGENT = "xiaoxiaoapi/1.0.0 (https://xxapi.cn)"
COMMON_HEADERS = {"User-Agent": USER_AGENT}

@register("astrbot_websitetool","wxgl","集成网站测试工具，支持连通性测试、速度测试、域名查询、端口扫描和截图。使用/sitehelp查看帮助","1.0")
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
        messages = event.get_messages()
        if not messages:
            return []

        message_text = messages[0].text.strip()
        parts = message_text.split(maxsplit=1)  # 只分割一次保留完整URL
        if len(parts) < min_args + 1:
            return []
        return parts[1].split()  # 允许后续参数自由分割

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
/ping <网址> - 测试网站连通性
/siteno <网址> - 测试网站延迟
/whois <域名> - 查询域名信息
/port <IP地址> - 端口扫描
/site <网址>  - 获取网站截图

示例:
/ping mcsqz.stay33.cn
/siteno https://mcsqz.stay33.cn
/whois mcsqz.stay33.cn
/port 8.8.8.8
/site https://mcsqz.stay33.cn"""
        return event.plain_result(help_text)

    @command("ping")
    async def check_ping(self, event: AstrMessageEvent) -> MessageEventResult:
        """检测网站连通性"""
        args = self.parse_command_args(event)
        if not args:
            return event.plain_result("请输入要测试的域名!\n示例: /ping mcsqz.stay33.cn")

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
            return event.plain_result("请输入要测试的网址!\n示例: /siteno https://mcsqz.stay33.cn")

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
            return event.plain_result("请输入要查询的域名!\n示例: /whois baidu.com")

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
            return event.plain_result("请输入网址!\n示例: /site https://mcsqz.stay33.cn")

        return await self.send_api_result(
            event,
            endpoint="screenshot",
            params={"url": args[0]},
            success_handler=lambda data: event.chain_result([
                Plain(f"截图成功：{data['msg']}\n"),
                Image.fromURL(data['data'])
            ])
        )

    async def on_unload(self):
        """插件卸载时关闭会话"""
        await self.session.close()
