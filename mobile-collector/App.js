import React from 'react';
import { StyleSheet, Text, View, TextInput, Button, TouchableOpacity } from 'react-native';
import { Camera, Permissions } from 'expo';
import base64 from 'base-64';
import ViewShot from "react-native-view-shot";

export default class App extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            hasCameraPermission: null,
            ipAddress: '',
            collectorId: '',
            storeId: '',
            isCapturing: false
        };
        this.isTakingPhoto = false;
    }

    async componentWillMount() {
        const { status } = await Permissions.askAsync(Permissions.CAMERA);
        this.setState({ hasCameraPermission: status === 'granted' });

        this.timer = setInterval(() => {
            if (this.state.isCapturing)
            {
                if (!this.isTakingPhoto) {
                    this.isTakingPhoto = true;
                    console.log("Taking photo", new Date());

                    const promise = this.camera.takePictureAsync({quality: 0.8, base64: true, skipProcessing: true});
                    promise.then((result) => {
                    // console.log(this.refs);
                    // return;
                    //     this.refs.viewShot.capture().then(uri => {
                    //     console.log("do something with ", uri);
                        this.isTakingPhoto = false;
                        // Make sure we are still capturing
                        if (this.state.isCapturing) {
                            console.log("Sending photo", new Date());
                            const url = 'http://' + this.state.ipAddress + ":1845/process_image";

                            const imageData = base64.decode(result.base64);

                            const formData = new FormData();
                            formData.append('image', imageData, "image.jpg");
                            formData.append('metadata', JSON.stringify({
                                "storeId": this.state.storeId,
                                "cameraId": this.state.collectorId,
                                "timestamp": new Date().toISOString().substr(new Date().toISOString().length - 1),
                                "cameraIndex": 0,
                                "record": true
                            }));

                            fetch(url, {
                                method: 'POST',
                                body: formData,
                            }).then(() => {
                                this.setState({timestamp: new Date()});
                            }, (err, response) => {
                                console.log(err);
                                console.log(response);
                                alert("Error uploading photo " + err.toString());
                                this.setState({isCapturing: false})
                            });
                        }
                    }, (err) => {
                        console.log(err);
                        console.log(response);
                        alert("Error taking photo " + err.toString());
                        this.setState({isCapturing: false})
                    });
                }
            }
        }, 500)
    }

    componentWillUnmount() {
        clearInterval(this.timer);
    }


    onTapStart = () => {
        if (this.camera) {

            const url = 'http://' + this.state.ipAddress + ":1806/register_collector";

            fetch(url, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    "storeId": this.state.storeId,
                    "collectorId": this.state.collectorId,
                    "cameras": [{"id": this.state.collectorId}]
                })
            }).then(() =>
            {
                this.setState({isCapturing: true})
            }, (err) => alert("Error Registering Collector" + err.toString()));
        }
    };

    onTapStop = () => {
        this.setState({isCapturing: false})
    };

  render() {
    return ( <View style={{padding: 20}}>
            <TextInput
                style={{height: 40}}
                placeholder="ipAddress"
                onChangeText={(text) => this.setState({ipAddress: text})}
            />
            <TextInput
                style={{height: 40}}
                placeholder="collectorId"
                onChangeText={(text) => this.setState({collectorId: text})}
            />
            <TextInput
                style={{height: 40}}
                placeholder="storeId"
                onChangeText={(text) => this.setState({storeId: text})}
            />

            {
                !this.state.isCapturing ?
                    <Button
                        onPress={this.onTapStart.bind(this)}
                        title="Start"
                        style={{"margin-top": 10, "margin-bottom": 10}}
                    />
                    :
                    <Button
                        onPress={this.onTapStop.bind(this)}
                        title="Stop"
                        style={{"margin-top": 10, "margin-bottom": 10}}
                    />
            }
            {
                this.state.hasCameraPermission ?
                    //<ViewShot ref="viewShot" options={{ format: "jpg", quality: 0.8, "captureMode": "mount" }} captureMode="mount" onCapture={() => null} >
                        <Camera
                            ref={(ref) => this.camera = ref}
                            type={Camera.Constants.Type.back}
                            autoFocus={Camera.Constants.AutoFocus.off}
                            style={{
                                "width": 300,
                                "height": 300,
                                "margin": 10
                            }} />
                    //</ViewShot>
                    : null
            }

            <Text>
                Is Capturing: {this.state.isCapturing.toString()}
            </Text>
            <Text>
                Last Successful Send: {this.state.timestamp ? this.state.timestamp.toString() : "none"}
            </Text>
          </View>
    );
  }
}

