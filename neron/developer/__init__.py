"""Developer agent and codebase self-improvement subsystem for Neron."""

from neron.developer.agent import DeveloperAgent
from neron.developer.backup import BackupManager, BackupMetadata
from neron.developer.introspector import CodeIntrospector
from neron.developer.patcher import (
    PatchGenerator,
    PatchValidationResult,
    PatchValidator,
)
from neron.developer.scaffolder import (
    PluginScaffoldConfig,
    PluginScaffolder,
)
from neron.developer.staging import StagingWorkspace
from neron.developer.test_runner import TestResult, TestRunner
from neron.developer.updater import DeploymentReport, SelfUpdatePipeline
from neron.developer.validator import ValidationGate, ValidationReport

__all__ = [
    "DeveloperAgent",
    "CodeIntrospector",
    "TestRunner",
    "TestResult",
    "PatchGenerator",
    "PatchValidator",
    "PatchValidationResult",
    "PluginScaffolder",
    "PluginScaffoldConfig",
    "StagingWorkspace",
    "BackupManager",
    "BackupMetadata",
    "ValidationGate",
    "ValidationReport",
    "SelfUpdatePipeline",
    "DeploymentReport",
]
