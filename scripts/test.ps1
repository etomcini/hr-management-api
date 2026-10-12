$composeFile = "compose.test.yaml"
$testExitCode = 1

try {
    docker compose -f $composeFile up `
        --build `
        --abort-on-container-exit `
        --exit-code-from tests

    $testExitCode = $LASTEXITCODE
}
finally {
    docker compose -f $composeFile down `
        --volumes `
        --remove-orphans
}

exit $testExitCode