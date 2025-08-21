# -*- coding: utf-8 -*-

"""
证书签发客户端

负责与证书签发服务器进行 API 交互，完成挑战-响应流程，并获取证书。
"""

import os
import requests
import base64
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

class CertificateClient:
    """封装了与证书颁发服务器所有交互的客户端"""

    def __init__(self, api_base_url: str):
        # 确保 URL 尾部没有斜杠，方便拼接
        self.base_url = api_base_url.rstrip('/')

    def issue_new_certificate(self, output_dir: str, node_id: str) -> tuple[bool, str]:
        """
        执行完整的证书签发流程 (CSR模式)，并将密钥和证书保存到指定目录。

        :param output_dir: 保存证书和私钥的目标目录。
        :param node_id: 节点的原始ID，用于API请求。
        :return: 一个元组 (success: bool, message: str)
        """
        try:
            # 确保输出目录存在
            conf_dir = os.path.join(output_dir, "conf")
            os.makedirs(conf_dir, exist_ok=True)
            key_path = os.path.join(conf_dir, "node.key")
            crt_path = os.path.join(conf_dir, "node.crt")
            ca_path = os.path.join(conf_dir, "ca.crt")

            # 1. 在客户端本地生成并保存私钥
            private_key = ec.generate_private_key(ec.SECP256R1())
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # 2. 从私钥派生公钥，并进行 Base64 编码用于请求挑战
            public_key = private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            public_key_b64 = base64.b64encode(public_key_pem).decode('utf-8')

            # 3. 请求挑战
            challenge_url = f"{self.base_url}/ca/request-challenge"
            response = requests.post(challenge_url, json={
                "original_node_id": node_id,
                "public_key": public_key_b64
            }, timeout=10)
            response.raise_for_status()
            challenge = response.json()["challenge"]

            # 4. 本地签名挑战
            signature = private_key.sign(challenge.encode('utf-8'), ec.ECDSA(hashes.SHA256()))
            signature_b64 = base64.b64encode(signature).decode('utf-8')

            # 5. 生成证书签名请求 (CSR)
            csr_builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, f'node.{node_id}'),
            ]))
            csr = csr_builder.sign(private_key, hashes.SHA256())
            csr_pem = csr.public_bytes(serialization.Encoding.PEM)
            csr_b64 = base64.b64encode(csr_pem).decode('utf-8')

            # 6. 请求签发证书 (发送 CSR)
            issue_url = f"{self.base_url}/ca/issue-certificate"
            response = requests.post(issue_url, json={
                "original_node_id": node_id,
                "csr": csr_b64,
                "challenge": challenge,
                "signature": signature_b64
            }, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 7. 解码并保存证书
            with open(crt_path, "wb") as f:
                f.write(base64.b64decode(data["certificate"]))
            with open(ca_path, "wb") as f:
                f.write(base64.b64decode(data["ca_bundle"]))
            
            return True, f"部署成功！证书和私钥已保存到 {conf_dir}"

        except requests.exceptions.RequestException as e:
            return False, f"网络请求失败: {e}"
        except Exception as e:
            return False, f"发生未知错误: {e}"

    def issue_console_sdk_certificate(self, output_conf_dir: str, node_id: str) -> tuple[bool, str]:
        """
        为控制台SDK执行完整的证书签发流程 (CSR模式)，并将密钥和证书保存到指定目录。
        生成的文件将被命名为 sdk.key, sdk.crt, ca.crt。

        :param output_conf_dir: 保存证书和私钥的目标目录 (通常是 console/conf)。
        :param node_id: 节点的原始ID，用于API请求和证书标识。
        :return: 一个元组 (success: bool, message: str)
        """
        try:
            # 确保输出目录存在
            os.makedirs(output_conf_dir, exist_ok=True)
            key_path = os.path.join(output_conf_dir, "sdk.key")
            crt_path = os.path.join(output_conf_dir, "sdk.crt")
            ca_path = os.path.join(output_conf_dir, "ca.crt")

            # 1. 在客户端本地生成并保存私钥
            private_key = ec.generate_private_key(ec.SECP256R1())
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # 2. 从私钥派生公钥，并进行 Base64 编码用于请求挑战
            public_key = private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            public_key_b64 = base64.b64encode(public_key_pem).decode('utf-8')

            # 3. 请求挑战
            challenge_url = f"{self.base_url}/ca/request-challenge"
            response = requests.post(challenge_url, json={
                "original_node_id": node_id,
                "public_key": public_key_b64
            }, timeout=10)
            response.raise_for_status()
            challenge = response.json()["challenge"]

            # 4. 本地签名挑战
            signature = private_key.sign(challenge.encode('utf-8'), ec.ECDSA(hashes.SHA256()))
            signature_b64 = base64.b64encode(signature).decode('utf-8')

            # 5. 生成证书签名请求 (CSR)
            csr_builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, f'console.sdk.{node_id}'),
            ]))
            csr = csr_builder.sign(private_key, hashes.SHA256())
            csr_pem = csr.public_bytes(serialization.Encoding.PEM)
            csr_b64 = base64.b64encode(csr_pem).decode('utf-8')

            # 6. 请求签发证书 (发送 CSR)
            issue_url = f"{self.base_url}/ca/issue-certificate"
            response = requests.post(issue_url, json={
                "original_node_id": node_id,
                "csr": csr_b64,
                "challenge": challenge,
                "signature": signature_b64
            }, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 7. 解码并保存证书
            with open(crt_path, "wb") as f:
                f.write(base64.b64decode(data["certificate"]))
            with open(ca_path, "wb") as f:
                f.write(base64.b64decode(data["ca_bundle"]))
            
            return True, f"控制台SDK证书签发成功！证书和私钥已保存到 {output_conf_dir}"

        except requests.exceptions.RequestException as e:
            return False, f"网络请求失败: {e}"
        except Exception as e:
            return False, f"发生未知错误: {e}"