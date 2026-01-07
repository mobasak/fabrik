"""Tests for spec validation."""

import pytest

from fabrik.orchestrator.exceptions import ValidationError
from fabrik.orchestrator.validator import SpecValidator, compute_spec_hash


class TestComputeSpecHash:
    """Test spec hashing."""

    def test_same_spec_same_hash(self):
        """Same spec content produces same hash."""
        spec = {"name": "test", "domain": "test.com"}
        hash1 = compute_spec_hash(spec)
        hash2 = compute_spec_hash(spec)
        assert hash1 == hash2

    def test_different_spec_different_hash(self):
        """Different spec content produces different hash."""
        spec1 = {"name": "test1", "domain": "test.com"}
        spec2 = {"name": "test2", "domain": "test.com"}
        assert compute_spec_hash(spec1) != compute_spec_hash(spec2)

    def test_hash_length(self):
        """Hash should be 16 characters."""
        spec = {"name": "test"}
        assert len(compute_spec_hash(spec)) == 16


class TestSpecValidator:
    """Test SpecValidator class."""

    def test_load_valid_spec(self, tmp_path):
        """Load a valid YAML spec file."""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text("name: test-app\ntemplate: python-api\ndomain: test.example.com\n")

        validator = SpecValidator()
        spec = validator.load_spec(spec_file)

        assert spec["name"] == "test-app"
        assert spec["domain"] == "test.example.com"

    def test_load_missing_file(self, tmp_path):
        """Raise ValidationError for missing file."""
        validator = SpecValidator()

        with pytest.raises(ValidationError) as exc:
            validator.load_spec(tmp_path / "nonexistent.yaml")

        assert "not found" in str(exc.value)

    def test_load_invalid_yaml(self, tmp_path):
        """Raise ValidationError for invalid YAML."""
        spec_file = tmp_path / "bad.yaml"
        spec_file.write_text("name: [invalid yaml")

        validator = SpecValidator()

        with pytest.raises(ValidationError) as exc:
            validator.load_spec(spec_file)

        assert exc.value.field == "syntax"

    def test_validate_missing_required_field(self):
        """Raise ValidationError for missing required fields."""
        validator = SpecValidator()
        spec = {"template": "python-api", "domain": "test.com"}

        with pytest.raises(ValidationError) as exc:
            validator.validate(spec)

        assert "name" in str(exc.value)

    def test_validate_invalid_name(self):
        """Raise ValidationError for invalid name format."""
        validator = SpecValidator()
        spec = {"name": "invalid name!", "template": "python-api", "domain": "test.com"}

        with pytest.raises(ValidationError) as exc:
            validator.validate(spec)

        assert exc.value.field == "name"

    def test_validate_invalid_domain(self):
        """Raise ValidationError for invalid domain."""
        validator = SpecValidator()
        spec = {"name": "test", "template": "python-api", "domain": "nodot"}

        with pytest.raises(ValidationError) as exc:
            validator.validate(spec)

        assert exc.value.field == "domain"

    def test_validate_secrets_must_be_list(self):
        """Raise ValidationError if secrets is not a list."""
        validator = SpecValidator()
        spec = {
            "name": "test",
            "template": "python-api",
            "domain": "test.com",
            "secrets": "not-a-list",
        }

        with pytest.raises(ValidationError) as exc:
            validator.validate(spec)

        assert exc.value.field == "secrets"

    def test_validate_valid_spec(self, tmp_path):
        """Valid spec passes validation."""
        validator = SpecValidator(templates_dir=tmp_path)

        # Create template dir
        (tmp_path / "python-api").mkdir()

        spec = {
            "name": "test-app",
            "template": "python-api",
            "domain": "test.example.com",
            "secrets": ["API_KEY"],
        }

        warnings = validator.validate(spec)
        assert warnings == []

    def test_load_and_validate(self, tmp_path):
        """Load, validate, and hash a spec in one call."""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text("name: test-app\ntemplate: python-api\ndomain: test.example.com\n")

        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        spec, spec_hash, warnings = validator.load_and_validate(spec_file)

        assert spec["name"] == "test-app"
        assert len(spec_hash) == 16
        assert isinstance(warnings, list)
