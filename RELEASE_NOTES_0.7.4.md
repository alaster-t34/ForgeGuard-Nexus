# ForgeGuard Nexus 5.0 v0.7.4

## Dependency compatibility correction

This release fixes a blocking packaging error in v0.7.3. The bundled vibration classifier was trained and serialized with scikit-learn 1.8.0, while the backend lock file incorrectly pinned scikit-learn 1.5.2. That older runtime cannot import `sklearn.frozen.FrozenEstimator` and cannot reliably load the bundled joblib artifact.

### Corrections

- Pin backend scikit-learn to exactly `1.8.0`.
- Require Python 3.11 or newer for the backend.
- Record the required scikit-learn version in the model card.
- Add a runtime compatibility guard with a clear error message.
- Add regression tests that load the bundled model under scikit-learn 1.8.0.
- Update Windows and Linux native installers to reject Python 3.10.
- Keep the Jetson edge client compatible with its existing host Python; the API backend continues to run in a Python 3.11 Docker container.

### Verified runtime

- scikit-learn: 1.8.0
- Bundled artifact: `selected_vibration_model.joblib`
- Model class: `CalibratedClassifierCV` with `FrozenEstimator` and `HistGradientBoostingClassifier`
