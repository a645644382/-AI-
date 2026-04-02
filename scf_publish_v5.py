# -*- coding: utf-8 -*-
"""
微信公众号发布云函数 v5
功能：接收 multipart 请求，转发图片到微信素材库，创建草稿
"""

import json
import re
import os
import uuid
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import http.client
import mimetypes


# ==================== 微信配置 ====================
APPID = "wx67f2438c4a816f67"
APPSECRET = "fb920b316ba61a04ec4b0595b8d2ff82"
# ================================================


def http_get(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"errcode": -1, "errmsg": f"GET请求失败: {str(e)}"}


def http_post_json(url, payload=None, timeout=15):
    """POST JSON请求"""
    try:
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"errcode": -1, "errmsg": f"POST JSON失败: {str(e)}"}


def encode_multipart_formdata(fields, files):
    """构建 multipart/form-data 请求体"""
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    body = b''

    # 添加字段
    for name, value in fields.items():
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += f'{value}\r\n'.encode()

    # 添加文件
    for name, (filename, file_data, content_type) in files.items():
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        body += f'Content-Type: {content_type}\r\n\r\n'.encode()
        body += file_data
        body += b'\r\n'

    # 结束
    body += f'--{boundary}--\r\n'.encode()

    content_type = f'multipart/form-data; boundary={boundary}'
    return body, content_type


def upload_to_wechat_urllib(token, file_path, file_name, file_type="image"):
    """使用 urllib.request 上传文件到微信素材库"""
    try:
        # 确保文件名有扩展名
        ext = os.path.splitext(file_name)[1].lower()
        if not ext or ext not in ('.jpg', '.jpeg', '.png', '.gif'):
            ext = ".jpg"
            file_name = file_name + ext

        content_type = 'image/jpeg'

        # 读取文件
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # 调试：验证文件本身
        print(f"[urllib] 文件: {file_name}, {len(file_data)} bytes, 头hex: {file_data[:10].hex()}")

        # 构建 multipart
        fields = {}
        files = {'media': (file_name, file_data, content_type)}
        body, content_type_header = encode_multipart_formdata(fields, files)

        header_end_idx = body.find(b'\r\n\r\n') + 4
        body_file_hex = body[header_end_idx:header_end_idx+10].hex()
        print(f"[urllib] Body: {len(body)} bytes, 文件hex: {body_file_hex}")

        # 使用 urllib.request（不加手动 Content-Type）
        api_url = f"https://api.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type={file_type}"

        req = urllib.request.Request(
            api_url,
            data=body,
            headers={
                'Content-Type': content_type_header,
                'User-Agent': 'Mozilla/5.0 (compatible; WeChatSCF/1.0)',
            },
            method='POST'
        )

        print(f"[urllib] 发送请求...")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_text = resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            resp_text = e.read().decode('utf-8')
            print(f"[urllib] HTTPError {e.code}: {resp_text[:500]}")

        print(f"[urllib] 响应: {resp_text[:500]}")

        # 把调试塞进返回
        result = json.loads(resp_text)
        result["_debug"] = {
            "file": file_name,
            "file_size": len(file_data),
            "body_size": len(body),
            "body_file_hex": body_file_hex,
            "content_type_sent": content_type_header,
        }
        return result
    except Exception as e:
        import traceback
        return {"errcode": -1, "errmsg": f"上传失败: {str(e)}", "detail": traceback.format_exc()[:500]}


def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    resp = http_get(url)
    if "access_token" not in resp:
        raise Exception(f"获取token失败: {resp}")
    return resp["access_token"]


def parse_multipart(headers, body):
    """
    解析 multipart/form-data
    返回: {
        'fields': {field_name: value},
        'files': {field_name: {'filename': xxx, 'content': bytes, 'content_type': xxx}}
    }
    """
    # 不区分大小写获取 Content-Type（腾讯云 SCF 可能返回小写 key）
    content_type = ""
    for k, v in headers.items():
        if k.lower() == "content-type":
            content_type = v
            break
    if not content_type:
        raise Exception(f"无法获取 Content-Type，headers keys: {list(headers.keys())}")

    # 提取 boundary
    boundary_match = re.search(r'boundary=(["\']?)(.+?)\1', content_type)
    if not boundary_match:
        raise Exception("无法解析 multipart boundary")

    boundary = ("--" + boundary_match.group(2)).encode()

    result = {"fields": {}, "files": {}}
    parts = body.split(boundary)

    for part in parts:
        if not part or part.strip() in (b"", b"--", b"--\r\n"):
            continue

        # 去掉末尾的 \r\n
        if part.endswith(b"\r\n--"):
            part = part[:-4]
        elif part.endswith(b"\r\n"):
            part = part[:-2]

        # 分离 header 和 body
        header_body_split = part.find(b"\r\n\r\n")
        if header_body_split == -1:
            continue

        header_part = part[:header_body_split]
        content_part = part[header_body_split + 4:]

        # 解析 header
        header_text = header_part.decode("utf-8", errors="replace")

        # 提取 field name
        name_match = re.search(r'name="([^"]*)"', header_text)
        if not name_match:
            continue
        field_name = name_match.group(1)

        # 检查是否有 filename（即文件）
        filename_match = re.search(r'filename="([^"]*)"', header_text)
        if filename_match:
            filename = filename_match.group(1)
            ct_match = re.search(r'Content-Type:\s*([^\r\n]+)', header_text)
            content_type_file = ct_match.group(1) if ct_match else "application/octet-stream"
            result["files"][field_name] = {
                "filename": filename,
                "content": content_part,
                "content_type": content_type_file
            }
        else:
            # 普通字段
            result["fields"][field_name] = content_part.decode("utf-8", errors="replace")

    return result


def create_draft(token, title, content, thumb_media_id, author="", digest=""):
    """创建微信草稿"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    payload = {
        "articles": [{
            "title": title,
            "thumb_media_id": thumb_media_id,
            "author": author,
            "digest": digest or title,
            "show_cover_pic": 1,
            "content": content,
            "content_source_url": ""
        }]
    }
    return http_post_json(url, payload)


def save_temp_file(data, suffix=".jpg"):
    """保存二进制数据到临时文件"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


def main_handler(event, context):
    """云函数入口"""
    print("[DEBUG] 云函数被调用")
    result_detail = {"step": "start", "ok": False}

    try:
        # 1. 解析请求
        headers = event.get("headers", {})
        body = event.get("body", b"")
        
        # 调试：打印原始 headers
        result_detail["raw_headers"] = dict(headers)

        # 调试：打印基本信息
        print(f"[DEBUG] headers keys: {list(headers.keys())}")
        print(f"[DEBUG] body type: {type(body)}, length: {len(body) if body else 0}")

        # 处理 body 格式
        if isinstance(body, str):
            # 如果是字符串，可能是 base64 编码
            if len(body) > 1024 * 1024:  # 超过 1MB 的字符串很可能是 base64
                import base64
                body = base64.b64decode(body)
            else:
                # 腾讯云 SCF 的 body 可能是 latin-1 编码的字符串
                body = body.encode("utf-8") if body else b""
        elif isinstance(body, dict):
            # SCF 某些情况下 body 是 dict
            is_base64 = body.get("isBase64Encoded", False)
            body_data = body.get("body", b"")
            if isinstance(body_data, str):
                body_data = body_data.encode("utf-8") if body_data else b""
            if is_base64 and body_data:
                import base64
                body = base64.b64decode(body_data)
            else:
                body = body_data
        elif body is None:
            body = b""

        result_detail["step"] = "parse_multipart"
        parsed = parse_multipart(headers, body)
        fields = parsed["fields"]
        files = parsed["files"]

        title = fields.get("title", "今日小满")
        digest_text = fields.get("digest", "")
        content = fields.get("content", "<p>今日小满</p>")

        result_detail["fields_received"] = list(fields.keys())
        result_detail["files_received"] = list(files.keys())

        if not files:
            raise Exception("没有收到任何图片文件")

        # 2. 获取 access_token
        result_detail["step"] = "get_token"
        token = get_access_token()
        result_detail["token_ok"] = True

        # 3. 上传封面（第一个图片文件作为封面）
        result_detail["step"] = "upload_cover"
        first_file_name = list(files.keys())[0]
        first_file = files[first_file_name]

        suffix = os.path.splitext(first_file["filename"])[1] or ".jpg"
        cover_path = save_temp_file(first_file["content"], suffix)
        cover_resp = upload_to_wechat_urllib(token, cover_path, first_file["filename"])

        # 清理临时文件
        try:
            os.unlink(cover_path)
        except:
            pass

        if cover_resp.get("errcode", 0) != 0:
            raise Exception(f"封面上传失败: {cover_resp}")
        thumb_media_id = cover_resp["media_id"]
        result_detail["cover_uploaded"] = thumb_media_id

        # 4. 上传正文图片并替换引用
        result_detail["step"] = "upload_content_images"
        content_images = {}  # field_name -> WeChat url
        processed_content = content

        for field_name, file_info in files.items():
            if field_name == first_file_name:
                continue  # 封面已经上传

            result_detail["step"] = f"upload_{field_name}"
            suffix = os.path.splitext(file_info["filename"])[1] or ".jpg"
            img_path = save_temp_file(file_info["content"], suffix)

            img_resp = upload_to_wechat_urllib(token, img_path, file_info["filename"])
            try:
                os.unlink(img_path)
            except:
                pass

            if img_resp.get("errcode", 0) != 0:
                result_detail["warn"] = f"图片 {field_name} 上传失败: {img_resp}，将被跳过"
                continue

            wechat_url = img_resp.get("url", "")
            if wechat_url:
                # 把 field_name 替换成 WeChat URL
                # HTML 里用 <img data-local="field_name" /> 作为占位
                processed_content = processed_content.replace(
                    f'data-local="{field_name}"',
                    f'src="{wechat_url}"'
                )
                content_images[field_name] = wechat_url

        result_detail["images_processed"] = len(content_images)
        result_detail["content_length"] = len(processed_content)

        # 5. 创建草稿
        result_detail["step"] = "create_draft"
        draft_resp = create_draft(token, title, processed_content, thumb_media_id, digest=digest_text)

        if draft_resp.get("errcode", 0) != 0:
            raise Exception(f"创建草稿失败: {draft_resp}")

        result_detail["step"] = "done"
        result_detail["ok"] = True
        result_detail["draft_msg_id"] = draft_resp.get("msg_id", "")
        result_detail["thumb_media_id"] = thumb_media_id
        result_detail["images_count"] = len(content_images)

        return {
            "statusCode": 200,
            "body": json.dumps(result_detail, ensure_ascii=False),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        result_detail["error"] = str(e)
        result_detail["trace"] = err_trace
        return {
            "statusCode": 500,
            "body": json.dumps(result_detail, ensure_ascii=False),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }
