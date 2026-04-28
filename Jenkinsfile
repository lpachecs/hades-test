pipeline {
    agent {
        docker {
            label 'docker-agent'
            image 'docker-cst-lab.lawo.de:5000/python-baseimage:3.11-slim'
        }
    }
 
    stages {

        stage('Install') {
            steps {
                script {
                    sh "pip install --upgrade pip"
                    sh "pip install poetry pytest"
                    withCredentials([usernamePassword(credentialsId: 'buildbot-https', passwordVariable: 'GITEA_PASS', usernameVariable: 'GITEA_USR')]) {
                        sh "poetry config http-basic.gitea-pypi $GITEA_USR $GITEA_PASS"
                        sh "poetry lock"
                        sh "poetry install"
                    }
                }
            }
        }

        stage('Test') {
            steps {
                script {
                    sh "poetry run python -m pytest tests/ -m \"not dependency\""
                }
            }
        }

        stage('Publish') {
            steps {
                script {
                    sh "git tag --list"
                    withCredentials([usernamePassword(credentialsId: 'buildbot-https', passwordVariable: 'GITEA_PASS', usernameVariable: 'GITEA_USR')]) {   
                        sh "poetry config http-basic.gitea-pub $GITEA_USR $GITEA_PASS"
                        sh "poetry publish --build --repository gitea-pub"
                    }
                }
            }
        }
    }
}