#!/bin/bash

# 颜色定义
RED='\e[0;31m'
GREEN='\e[0;32m'
YELLOW='\e[1;33m'
BLUE='\e[0;34m'
CYAN='\e[0;36m'
PURPLE='\e[0;35m'
NC='\e[0m' # No Color

# 检测终端颜色支持
if [[ ! -t 1 ]] || [[ "${TERM}" == "dumb" ]]; then
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    CYAN=""
    PURPLE=""
    NC=""
fi

# 显示横幅
show_banner() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "           Docker 应用管理脚本 v3.0"
    echo "=================================================="
    echo -e "${NC}"
}

# 交互式选择环境
select_environment() {
    echo "" >&2
    echo -e "${CYAN}🌍 请选择运行环境:${NC}" >&2
    echo -e "${YELLOW}  1)${NC} 开发环境 (dev)   - 带热重载，完整日志输出" >&2
    echo -e "${YELLOW}  2)${NC} 生产环境 (prod)  - 优化性能，生产级配置" >&2
    echo "" >&2
    
    while true; do
        read -p "请输入选择 [1-2]: " env_choice
        case $env_choice in
            1)
                echo "dev"
                return
                ;;
            2)
                echo "prod"
                return
                ;;
            *)
                echo -e "${RED}❌ 无效选择，请输入 1 或 2${NC}" >&2
                ;;
        esac
    done
}

# 交互式选择操作
select_action() {
    echo "" >&2
    echo -e "${CYAN}⚡ 请选择要执行的操作:${NC}" >&2
    echo -e "${YELLOW}  1)${NC} 🚀 启动服务           - 启动所有容器服务" >&2
    echo -e "${YELLOW}  2)${NC} 🛑 停止服务           - 停止所有运行中的容器" >&2  
    echo -e "${YELLOW}  3)${NC} 🔄 重启服务           - 重启所有容器服务" >&2
    echo -e "${YELLOW}  4)${NC} 📋 查看实时日志       - 实时显示服务日志" >&2
    echo -e "${YELLOW}  5)${NC} 📊 查看服务状态       - 显示各服务运行状态" >&2
    echo -e "${YELLOW}  6)${NC} 🔨 重新构建并启动     - 重建镜像后启动服务" >&2
    echo -e "${YELLOW}  7)${NC} 🗑️  停止并清理数据卷   - 停止服务并删除所有数据" >&2
    echo -e "${YELLOW}  8)${NC} 🧹 彻底清理系统       - 清理所有Docker资源(镜像/容器/卷/网络)" >&2
    echo -e "${YELLOW}  9)${NC} ❓ 显示帮助信息       - 查看详细使用说明" >&2
    echo "" >&2
    
    while true; do
        read -p "请输入选择 [1-9]: " action_choice
        case $action_choice in
            1)
                echo "up"
                return
                ;;
            2)
                echo "down"
                return
                ;;
            3)
                echo "restart"
                return
                ;;
            4)
                echo "logs"
                return
                ;;
            5)
                echo "status"
                return
                ;;
            6)
                echo "build"
                return
                ;;
            7)
                echo "down-volumes"
                return
                ;;
            8)
                echo "system-prune"
                return
                ;;
            9)
                echo "help"
                return
                ;;
            *)
                echo -e "${RED}❌ 无效选择，请输入 1-9${NC}" >&2
                ;;
        esac
    done
}

# 检查必要工具
check_requirements() {
    local missing=0
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker 未安装${NC}"
        missing=1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose 未安装${NC}"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        echo -e "${RED}请先安装必要的工具${NC}"
        exit 1
    fi
}

# 获取compose文件
get_compose_files() {
    local env=$1
    if [ "$env" = "prod" ]; then
        echo "-f docker-compose.prod.yml"
    else
        echo "-f docker-compose.dev.yml"
    fi
}

# 获取环境文件
get_env_file() {
    local env=$1
    if [ "$env" = "prod" ]; then
        echo ".env.prod"
    else
        echo ".env.dev"
    fi
}

# 检查环境文件是否存在
check_env_file() {
    local env_file=$1
    if [ ! -f "$env_file" ]; then
        echo -e "${RED}❌ 环境配置文件不存在: $env_file${NC}"
        echo -e "${YELLOW}💡 请创建该文件，可参考 .env.example${NC}"
        exit 1
    fi
}

# 执行Docker操作
execute_docker_command() {
    local env=$1
    local action=$2
    local compose_files=$(get_compose_files $env)
    local env_file=$(get_env_file $env)
    
    # 检查环境文件
    check_env_file "$env_file"
    
    echo ""
    echo -e "${PURPLE}环境:${NC} ${env}"
    echo -e "${PURPLE}配置文件:${NC} ${compose_files}"
    echo -e "${PURPLE}环境变量:${NC} ${env_file}"
    echo -e "${PURPLE}当前目录:${NC} $(pwd)"
    echo ""
    
    case $action in
        "up")
            echo -e "${BLUE}🚀 启动 ${env} 环境服务...${NC}"
            echo -e "${CYAN}[DEBUG] 执行命令: docker compose $compose_files --env-file $env_file up -d${NC}"
            docker compose $compose_files --env-file $env_file up -d
            ;;
        "down")
            echo -e "${YELLOW}🛑 停止 ${env} 环境服务...${NC}"
            docker compose $compose_files down
            ;;
        "restart")
            echo -e "${YELLOW}🔄 重启 ${env} 环境服务...${NC}"
            docker compose $compose_files restart
            ;;
        "logs")
            echo -e "${CYAN}📋 查看 ${env} 环境日志...${NC}"
            echo -e "${YELLOW}按 Ctrl+C 退出日志查看${NC}"
            docker compose $compose_files logs -f
            ;;
        "status")
            echo -e "${CYAN}📊 查看 ${env} 环境状态...${NC}"
            docker compose $compose_files ps
            ;;
        "build")
            echo -e "${BLUE}🔨 构建并启动 ${env} 环境服务...${NC}"
            echo -e "${CYAN}[DEBUG] 执行命令: docker compose $compose_files --env-file $env_file up --build -d${NC}"
            docker compose $compose_files --env-file $env_file up --build -d
            ;;
        "down-volumes")
            echo -e "${RED}🗑️  停止服务并清理卷 (${env} 环境)...${NC}"
            echo -e "${YELLOW}⚠️  这将删除所有数据卷，请确认！${NC}"
            read -p "确认删除？(y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                docker compose $compose_files down -v
                echo -e "${GREEN}✅ 清理完成${NC}"
            else
                echo -e "${YELLOW}❌ 操作已取消${NC}"
            fi
            ;;
        "system-prune")
            echo -e "${RED}🧹 彻底清理Docker系统...${NC}"
            echo -e "${YELLOW}⚠️  这将删除以下所有内容:${NC}"
            echo -e "${YELLOW}   • 所有停止的容器${NC}"
            echo -e "${YELLOW}   • 所有未使用的网络${NC}"
            echo -e "${YELLOW}   • 所有未使用的镜像（包括有标签的）${NC}"
            echo -e "${YELLOW}   • 所有未使用的构建缓存${NC}"
            echo -e "${YELLOW}   • 所有未使用的数据卷${NC}"
            echo ""
            echo -e "${RED}⚠️  这将释放大量磁盘空间，但会删除所有数据！${NC}"
            read -p "确认执行彻底清理？(y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                echo -e "${CYAN}[DEBUG] 执行命令: docker system prune -a --volumes -f${NC}"
                docker system prune -a --volumes -f
                echo -e "${GREEN}✅ 系统清理完成${NC}"
            else
                echo -e "${YELLOW}❌ 操作已取消${NC}"
            fi
            ;;
        "help")
            show_detailed_help "$env"
            ;;
        *)
            echo -e "${RED}❌ 未知操作: $action${NC}"
            exit 1
            ;;
    esac
}

# 显示操作结果
show_result() {
    local env=$1
    local action=$2
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ 操作成功完成！${NC}"
        
        if [[ "$action" == "up" || "$action" == "build" ]]; then
            echo ""
            echo -e "${CYAN}🌐 服务访问地址:${NC}"
            if [ "$env" = "dev" ]; then
                echo -e "  主应用: ${YELLOW}http://localhost${NC}"
                echo -e "  PgAdmin: ${YELLOW}http://localhost:5050${NC}"
                echo -e "  RabbitMQ: ${YELLOW}http://localhost:15672${NC}"
                echo -e "  RedisInsight: ${YELLOW}http://localhost:8001${NC}"
            else
                echo -e "  主应用: ${YELLOW}http://localhost${NC}"
                echo -e "  PgAdmin: ${YELLOW}http://localhost:5050${NC}"
                echo -e "  RabbitMQ: ${YELLOW}http://localhost:15672${NC}"
                echo -e "  RedisInsight: ${YELLOW}http://localhost:8001${NC}"
            fi
            
            echo ""
            echo -e "${CYAN}📋 常用命令:${NC}"
            echo -e "  查看状态: ${YELLOW}./scripts/start.sh${NC}"
            echo -e "  查看日志: ${YELLOW}docker compose $(get_compose_files $env) logs -f [service_name]${NC}"
        fi
    else
        echo ""
        echo -e "${RED}❌ 操作执行失败！${NC}"
        exit 1
    fi
}

# 命令行参数处理
parse_args() {
    ENV=""
    ACTION=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--env)
                ENV="$2"
                shift 2
                ;;
            -a|--action)
                ACTION="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 未知参数: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

# 显示详细帮助信息
show_detailed_help() {
    local env=$1
    echo ""
    echo -e "${CYAN}===============================================${NC}"
    echo -e "${CYAN}         📚 Docker 应用管理详细帮助${NC}"
    echo -e "${CYAN}===============================================${NC}"
    echo ""
    
    echo -e "${YELLOW}🌍 当前环境: ${GREEN}${env}${NC}"
    echo ""
    
    echo -e "${YELLOW}📋 可用操作详解:${NC}"
    echo -e "${GREEN}  1. 启动服务 (up)${NC}"
    echo -e "     • 启动所有容器服务"
    echo -e "     • 如果容器已存在，会使用现有容器"
    echo -e "     • 适合日常开发使用"
    echo ""
    
    echo -e "${GREEN}  2. 停止服务 (down)${NC}"
    echo -e "     • 停止并移除所有容器"
    echo -e "     • 保留数据卷和网络"
    echo -e "     • 数据不会丢失"
    echo ""
    
    echo -e "${GREEN}  3. 重启服务 (restart)${NC}"
    echo -e "     • 重启所有运行中的容器"
    echo -e "     • 不重建镜像，快速重启"
    echo -e "     • 适合配置文件修改后的重启"
    echo ""
    
    echo -e "${GREEN}  4. 查看实时日志 (logs)${NC}"
    echo -e "     • 实时显示所有服务的日志输出"
    echo -e "     • 按 Ctrl+C 退出日志查看"
    echo -e "     • 有助于调试和监控"
    echo ""
    
    echo -e "${GREEN}  5. 查看服务状态 (status)${NC}"
    echo -e "     • 显示各服务运行状态"
    echo -e "     • 包含端口映射信息"
    echo -e "     • 快速了解系统健康状态"
    echo ""
    
    echo -e "${GREEN}  6. 重新构建并启动 (build)${NC}"
    echo -e "     • 重建所有Docker镜像"
    echo -e "     • 然后启动服务"
    echo -e "     • 适合代码更新或依赖变更后使用"
    echo ""
    
    echo -e "${RED}  7. 停止并清理数据卷 (down-volumes)${NC}"
    echo -e "     • ⚠️  危险操作：会删除所有数据！"
    echo -e "     • 停止服务并删除所有数据卷"
    echo -e "     • 用于完全重置环境"
    echo ""
    
    echo -e "${YELLOW}🌐 服务访问地址:${NC}"
    if [ "$env" = "dev" ]; then
        echo -e "  主应用:      ${CYAN}http://localhost${NC}"
        echo -e "  PgAdmin:     ${CYAN}http://localhost:5050${NC} (数据库管理)"
        echo -e "  RabbitMQ:    ${CYAN}http://localhost:15672${NC} (消息队列管理)"
        echo -e "  RedisInsight: ${CYAN}http://localhost:8001${NC} (Redis管理)"
    else
        echo -e "  主应用:      ${CYAN}http://localhost${NC}"
        echo -e "  PgAdmin:     ${CYAN}http://localhost:5050${NC} (数据库管理)"
        echo -e "  RabbitMQ:    ${CYAN}http://localhost:15672${NC} (消息队列管理)"
        echo -e "  RedisInsight: ${CYAN}http://localhost:8001${NC} (Redis管理)"
    fi
    echo ""
    
    echo -e "${YELLOW}⚡ 快速命令:${NC}"
    echo -e "  查看特定服务日志: ${CYAN}docker compose $(get_compose_files $env) logs -f [service_name]${NC}"
    echo -e "  进入容器shell:   ${CYAN}docker compose $(get_compose_files $env) exec [service_name] /bin/bash${NC}"
    echo -e "  查看资源使用:     ${CYAN}docker stats${NC}"
    echo ""
    
    echo -e "${YELLOW}📁 环境文件:${NC}"
    echo -e "  配置文件: ${GREEN}$(get_compose_files $env)${NC}"
    echo -e "  环境变量: ${GREEN}$(get_env_file $env)${NC}"
    echo ""
    
    read -p "按回车键返回主菜单..." dummy
}

# 显示帮助信息
show_help() {
    echo -e "${YELLOW}使用说明:${NC}"
    echo "  $0                      # 交互式选择"
    echo "  $0 [选项]               # 命令行模式"
    echo ""
    echo -e "${YELLOW}选项:${NC}"
    echo "  -e, --env ENV           指定环境 (dev|prod)"
    echo "  -a, --action ACTION     指定操作 (up|down|restart|logs|status|build|down-volumes|system-prune|help)"
    echo "  -h, --help              显示此帮助信息"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  $0                           # 交互式选择"
    echo "  $0 --env dev --action up     # 启动开发环境"
    echo "  $0 --env prod --action build # 构建并启动生产环境"
    echo "  $0 --env dev --action help   # 显示详细帮助"
}

# 主函数
main() {
    show_banner
    check_requirements
    
    # 解析命令行参数
    parse_args "$@"
    
    # 如果有命令行参数，直接执行
    if [ -n "$ENV" ] && [ -n "$ACTION" ]; then
        execute_docker_command "$ENV" "$ACTION"
        if [ "$ACTION" != "help" ]; then
            show_result "$ENV" "$ACTION"
        fi
        return
    fi
    
    # 交互式模式循环
    while true; do
        # 选择环境（只在第一次或重新开始时选择）
        if [ -z "$ENV" ]; then
            ENV=$(select_environment)
        fi
        
        # 选择操作
        ACTION=$(select_action)
        
        # 执行操作
        execute_docker_command "$ENV" "$ACTION"
        
        # 显示结果（帮助操作不需要显示结果）
        if [ "$ACTION" != "help" ]; then
            show_result "$ENV" "$ACTION"
            
            # 询问是否继续
            echo ""
            echo -e "${CYAN}是否要执行其他操作？${NC}"
            echo -e "${YELLOW}1)${NC} 继续使用当前环境 ($ENV)"
            echo -e "${YELLOW}2)${NC} 切换到其他环境"
            echo -e "${YELLOW}3)${NC} 退出脚本"
            echo ""
            
            while true; do
                read -p "请输入选择 [1-3]: " continue_choice
                case $continue_choice in
                    1)
                        # 继续使用当前环境
                        break
                        ;;
                    2)
                        # 重新选择环境
                        ENV=""
                        break
                        ;;
                    3)
                        # 退出
                        echo -e "${GREEN}👋 感谢使用，再见！${NC}"
                        exit 0
                        ;;
                    *)
                        echo -e "${RED}❌ 无效选择，请输入 1-3${NC}"
                        ;;
                esac
            done
        fi
    done
}

# 运行主函数
main "$@"