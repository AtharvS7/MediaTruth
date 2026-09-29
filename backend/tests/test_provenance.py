from PIL import Image
from inference_pipeline.provenance import inspect_provenance


def test_unsigned_image_is_absent_not_authentic(tmp_path):
    path = tmp_path / 'ordinary.png'
    Image.new('RGB', (20, 20)).save(path)
    result = inspect_provenance(str(path))
    assert result['status'] == 'absent'
    assert result['network_access'] is False
    assert result['watermark_status'] == 'not_checked'
    assert result['actions'] == []


def test_corrupt_data_never_becomes_verified(tmp_path):
    path = tmp_path / 'broken.jpg'
    path.write_bytes(b'not an image')
    assert inspect_provenance(str(path))['status'] not in ('trusted', 'valid_untrusted')


def test_signed_actions_and_pixel_tampering(tmp_path, monkeypatch):
    """Generate ephemeral test certificates; no keys or outside media are stored in Git."""
    import datetime
    import json
    import struct
    import zlib
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from c2pa import Builder, Signer, C2paSignerInfo, Context
    now = datetime.datetime.now(datetime.timezone.utc)
    root_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'MediaTruth ephemeral test CA')])
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'MediaTruth test signer')])
    def certificate(subject, key, is_ca):
        builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(root_name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - datetime.timedelta(days=1))
                   .not_valid_after(now + datetime.timedelta(days=1))
                   .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
                   .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
                   .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), False)
                   .add_extension(x509.KeyUsage(digital_signature=not is_ca, content_commitment=False,
                       key_encipherment=False, data_encipherment=False, key_agreement=False,
                       key_cert_sign=is_ca, crl_sign=is_ca, encipher_only=None, decipher_only=None), True))
        if not is_ca:
            builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), False)
        return builder.sign(root_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode()
    root_pem = certificate(root_name, root_key, True)
    chain = certificate(leaf_name, leaf_key, False) + root_pem
    private = leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
    source, signed = tmp_path / 'source.png', tmp_path / 'signed.png'
    Image.new('RGB', (20, 20), 'red').save(source)
    manifest = json.dumps({'claim_generator': 'MediaTruth tests', 'title': 'generated fixture',
                          'assertions': [{'label': 'c2pa.actions', 'data': {'actions': [
                              {'action': 'c2pa.created', 'digitalSourceType':
                               'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'}]}}]})
    with Context.from_dict({'verify': {'remote_manifest_fetch': False, 'ocsp_fetch': False}}) as context:
        with Signer.from_info(C2paSignerInfo('es256', chain.encode(), private.encode(), None)) as signer:
            with Builder(manifest, context=context) as builder:
                with source.open('rb') as src, signed.open('w+b') as dest:
                    builder.sign(signer, 'image/png', src, dest)
    result = inspect_provenance(str(signed))
    assert result['status'] == 'valid_untrusted'
    assert any(action['action'] == 'c2pa.created' for action in result['actions'])
    original_context = Context.from_dict
    with monkeypatch.context() as patch:
        patch.setattr(Context, 'from_dict', staticmethod(lambda settings: original_context({
            **settings, 'trust': {'trust_anchors': root_pem},
        })))
        assert inspect_provenance(str(signed))['status'] == 'trusted'
    data = signed.read_bytes()
    output = bytearray(data[:8])
    cursor = 8
    changed = False
    while cursor < len(data):
        length = struct.unpack('>I', data[cursor:cursor + 4])[0]
        kind = data[cursor + 4:cursor + 8]
        payload = data[cursor + 8:cursor + 8 + length]
        if kind == b'IDAT' and not changed:
            pixels = bytearray(zlib.decompress(payload))
            pixels[-1] ^= 1
            payload = zlib.compress(pixels)
            changed = True
        output.extend(struct.pack('>I', len(payload)) + kind + payload +
                      struct.pack('>I', zlib.crc32(kind + payload)))
        cursor += length + 12
    assert changed
    signed.write_bytes(output)
    assert inspect_provenance(str(signed))['status'] == 'invalid'
