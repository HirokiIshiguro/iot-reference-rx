/***********************************************************************************************************************
* File Name    : code_signer_public_key.h
* Description  : PEM-encoded ECDSA (P-256) public key used to verify firmware signatures.
*
*                This file is a TEMPLATE. Copy it into your project and replace the key body below with the
*                public half of the key pair used to sign your firmware images (mot_to_rsu.py --key <priv.pem>).
*
*                Format: PEM with "-----BEGIN PUBLIC KEY-----" / "-----END PUBLIC KEY-----" guards.
***********************************************************************************************************************/

#ifndef CODE_SIGNER_PUBLIC_KEY_H_
#define CODE_SIGNER_PUBLIC_KEY_H_

#define CODE_SIGNER_PUBLIC_KEY_PEM \
"-----BEGIN PUBLIC KEY-----"\
"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE<REPLACE_WITH_YOUR_PUBLIC_KEY>"\
"-----END PUBLIC KEY-----"\

extern const uint8_t  code_signer_public_key[];
extern const uint32_t code_signer_public_key_length;

#endif /* CODE_SIGNER_PUBLIC_KEY_H_ */
