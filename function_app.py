import json
import azure.functions as func

# HTTP トリガー
from functions.httpTriggers.http_trigger import http_trigger

# MCP トリガー (basic tools)
from functions.mcpTriggers.hello_time_mcp import (
	hello_world_mcp,
	get_current_time_mcp,
)
from functions.mcpTriggers.course_search_mcp import (
	search_courses_by_name_mcp,
	search_courses_by_description_mcp,
	search_courses_by_company_mcp,
)
from functions.mcpTriggers.survey_query_mcp import (
	query_surveys_mcp,
)
from functions.mcpTriggers.course_list_mcp import (
	list_all_courses_mcp,
)
from functions.mcpTriggers.user_query_mcp import (
	get_users_by_ids_mcp,
	get_users_by_company_mcp,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------- HTTP Routes ----------------
app.route(route="http_trigger")(http_trigger)

# ---------------- MCP: Hello World ----------------
hello_props = json.dumps([
	{"propertyName": "name", "propertyType": "string", "description": "Optional name to greet"}
])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="hello_world",
	description="Returns a simple Hello World message",
	toolProperties=hello_props,
)(hello_world_mcp)

# ---------------- MCP: Current Time ----------------
time_props = json.dumps([])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="get_current_time",
	description="現在の UTC 時刻を ISO8601 で返します。",
	toolProperties=time_props,
)(get_current_time_mcp)

# ---------------- MCP: List All Courses ----------------
list_all_courses_props = json.dumps([])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="list_all_courses",
	description="研修した講座の情報 （Id(courseId), courseName, description, targetCompany, conductedAt）を 最大1000件 取得します。courseIdやuserIdも返却されます。",
	toolProperties=list_all_courses_props,
)(list_all_courses_mcp)

# ---------------- MCP: Course Searches ----------------
search_common_props = json.dumps([
	{"propertyName": "searchTerm", "propertyType": "string", "description": "検索語 (必須)"},
	{"propertyName": "topK", "propertyType": "integer", "description": "最大返却件数 (default 5)"},
])

app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="search_courses_by_name",
	description="研修講座の内容を、講座名 (courseName) を対象にあいまい検索します。Id(courseId), courseName, description, targetCompany, conductedAt が返却されます。",
	toolProperties=search_common_props,
)(search_courses_by_name_mcp)

app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="search_courses_by_description",
	description="研修講座の内容を、講座概要 (description) を対象にあいまい検索します。Id(courseId), courseName, description, targetCompany, conductedAt が返却されます。",
	toolProperties=search_common_props,
)(search_courses_by_description_mcp)

app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="search_courses_by_company",
	description="研修講座の内容を、対象会社名 (targetCompany) を対象にあいまい検索します。Id(courseId), courseName, description, targetCompany, conductedAt が返却されます。",
	toolProperties=search_common_props,
)(search_courses_by_company_mcp)

# ---------------- MCP: Survey Query ----------------
survey_query_props = json.dumps([
	{"propertyName": "courseId", "propertyType": "string", "description": "講座ID (courses.id) 単一。courseIdのみで検索可能"},
	{"propertyName": "userId", "propertyType": "string", "description": "ユーザID (users.id) 単一。userIdのみで検索可能"},
	{"propertyName": "topK", "propertyType": "integer", "description": "最大取得件数 (default 20)"},
])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="query_surveys",
	description="courseId または userId をキーに 研修講座のアンケート結果を取得します。",
	toolProperties=survey_query_props,
)(query_surveys_mcp)

# ---------------- MCP: User Queries ----------------
users_by_ids_props = json.dumps([
	{"propertyName": "userIds", "propertyType": "string", "description": "取得したいユーザIDのカンマ区切り文字列 (例: id1,id2,id3)"}
])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="get_users_by_ids",
	description="研修を受講したユーザ情報（会社名、部署、役職）を取得します。userIds のリストに該当するユーザ情報を返却します。",
	toolProperties=users_by_ids_props,
)(get_users_by_ids_mcp)

users_by_company_props = json.dumps([
	{"propertyName": "companyName", "propertyType": "string", "description": "会社名 (完全一致)"},
	{"propertyName": "topK", "propertyType": "integer", "description": "最大返却件数 (default 200)"}
])
app.generic_trigger(
	arg_name="context",
	type="mcpToolTrigger",
	toolName="get_users_by_company",
	description="研修を受講したユーザ情報（会社名、部署、役職）を取得します。companyName に一致するユーザを userName の昇順で取得します。",
	toolProperties=users_by_company_props,
)(get_users_by_company_mcp)

__all__ = ["app"]