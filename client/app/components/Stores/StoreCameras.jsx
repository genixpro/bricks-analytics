import React from 'react';
import {Col, Row, Panel, Alert} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {branch} from "recompose";
import ReactTable from 'react-table'
import _ from 'underscore';
import axios from "axios/index";
import {Stomp} from 'stompjs/lib/stomp.min';

class StoreCameras extends React.Component {
    constructor(props) {
        super(props);

        this.camera = _.findWhere(this.props.store.cameras, {id: this.props.match.params.cameraId});

        this.state = {
            selectedCamera: this.props.match.params.cameraId,
            cameraImageCacheBuster: Date.now().toString(),
            cameraFrame: null,
            isSelectingCameraLocation: false,
            isSelectingCalibrationObjectLocation: false,
            cameraX: 0,
            cameraY: 0,
            cameraRotation: 0,
            calibrationObjectX: 0,
            calibrationObjectY: 0,
            calibrationObjectRotation: 0
        };

        if (this.camera) {
            var headers = {durable: false, "auto-delete": false, exclusive: false};
            this.cameraSubscription = this.props.messagingClient.subscribe("/exchange/" + this.camera.cameraId, (message) =>
            {
                const body = JSON.parse(message.body);
                if (body.type === 'image-updated')
                {
                    this.reloadCameraImage();
                    this.reloadCameraFrameInformation();
                }
            }, headers);

            // Load the initial camera frame information right off the bat
            this.reloadCameraFrameInformation();

            // Load in the cameras current position into state variables so it can be edited
            this.state.cameraX = this.camera.cameraX || 0;
            this.state.cameraY = this.camera.cameraY || 0;
            this.state.cameraRotation= this.camera.cameraRotation || 0;
        }
    }

    /**
     * This function will cause the camera to reload the latest processed frame information. This is basically the
     * data that results from processing that image using the various computer-vision algorithms.
     */
    reloadCameraFrameInformation()
    {
        axios({
            method: 'get',
            url: `/store/${this.props.store._id}/cameras/${this.camera.cameraId}/frame/current`
        }).then((response) =>
        {
            this.setState({cameraFrame: response.data});
        });
    }


    /**
     * This function causes the browser to reload and display the latest image for this camera
     * thats stored in the database. This is different from triggerCameraRecordImage
     * in that triggerCameraRecordImage sends a message to the camera, through our API,
     * causing the camera itself to upload a fresh image. This method is only used
     * to download that image and display it after is has been uploaded by the camera.
     */
    reloadCameraImage()
    {
        // Reload the camera image by changing the cache-buster query
        this.setState({cameraImageCacheBuster: Date.now()});
    }

    /**
     * This method causes the selected Camera to record an image to the database, which will
     * in turn cause that latest image to be loaded in the browser.
     */
    triggerCameraRecordImage()
    {
        axios({
            method: 'post',
            url: `/store/${this.props.store._id}/cameras/${this.camera.cameraId}/record`
        })
    }

    /**
     * Triggered when this component appears on the screen.
     */
    componentDidMount()
    {
        if (this.camera)
        {
            this.triggerCameraRecordImage();
            this.updateInterval = setInterval(() => this.triggerCameraRecordImage(), 2500);
        }
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.cameraSubscription)
        {
            this.cameraSubscription.unsubscribe();
        }
        if (this.updateInterval)
        {
            clearInterval(this.updateInterval);
        }
    }


    /**
     * This function starts the calibration process
     */
    calibrateCameraClicked(event)
    {
        document.getElementById('store-layout').scrollIntoView(true);
        this.setState({isSelectingCameraLocation: true});
    }

    /**
     * This method gets called anytime the mouse is moving within the store layout image.
     * Used for calibration.
     *
     * @returns {*}
     */
    mouseMovedOnStoreLayout(event) {
        if (this.state.isSelectingCameraLocation)
        {
            const bounds = document.getElementById('store-image-container').getBoundingClientRect();
            const cameraX = event.clientX - bounds.left;
            const cameraY = event.clientY - bounds.top;

            this.setState({cameraX, cameraY});
        }
        else if (this.state.isSelectingCalibrationObjectLocation)
        {
            const bounds = document.getElementById('store-image-container').getBoundingClientRect();
            const calibrationObjectX = event.clientX - bounds.left;
            const calibrationObjectY = event.clientY - bounds.top;

            this.setState({calibrationObjectX, calibrationObjectY});
            this.updateCalibrationRotation();
        }
    }

    /**
     * This function is called when the user has set a new camera location during camera calibration
     */
    cameraLocationChosen()
    {
        if (this.state.isSelectingCameraLocation)
        {
            this.setState({
                isSelectingCameraLocation: false,
                isSelectingCalibrationObjectLocation: true,
                calibrationObjectX: this.state.cameraX,
                calibrationObjectY: this.state.cameraY
            });
        }
    }

    calibrationObjectLocationChosen()
    {
        if (this.state.isSelectingCalibrationObjectLocation)
        {
            this.setState({
                isSelectingCameraLocation: false,
                isSelectingCalibrationObjectLocation: false
            });
            this.updateCalibrationRotation();

            // Make the modification to the camera data.
            const newStore = this.props.store;
            const camera = _.findWhere(newStore.cameras, {id: this.state.selectedCamera});
            camera.cameraX = this.state.cameraX;
            camera.cameraY = this.state.cameraY;
            camera.cameraRotation = this.state.cameraRotation;

            console.log(this.state.cameraFrame);

            camera.cameraMatrix = this.state.cameraFrame.calibrationObject.cameraMatrix;
            camera.rotationVector = this.state.cameraFrame.calibrationObject.rotationVector;
            camera.translationVector = this.state.cameraFrame.calibrationObject.translationVector;

            this.props.updateStore(newStore);
        }
    }

    /**
     * This function updates the rotation on both the camera and the
     * calibration object.
     */
    updateCalibrationRotation()
    {
        const angle = Math.atan2(this.state.calibrationObjectY - this.state.cameraY, this.state.calibrationObjectX - this.state.cameraX);
        this.setState({cameraRotation: angle});
    }



    render() {
        const cameraImageOffsetX = 40;
        const cameraImageOffsetY = 20;

        const checkerboardImageOffsetX = 50;
        const checkerboardImageOffsetY = 50;

        return (
            <div className="store-cameras">
                <br/>
                <Row>
                    <Col md={3}>
                        <div className="panel b">
                            <div className="panel-body">
                                <strong className="text-muted">Cameras</strong>
                            </div>
                            <div className="list-group">
                                {
                                    this.props.store.cameras &&
                                    this.props.store.cameras.map((camera) =>
                                        <Link key={camera.cameraId} to={"/store/" + this.props.store._id + "/camera/" + camera.cameraId}
                                           className={"list-group-item " + (camera.cameraId === this.state.selectedCamera ? " active" : "")}>
                                            <span>{camera.cameraId}</span>
                                        </Link>
                                    )
                                }
                            </div>
                        </div>
                    </Col>
                    {this.camera &&
                    <Col md={9}>
                        <div className="row">
                            <div className="panel b">
                                <div className="panel-heading">
                                    <div className="pull-right">
                                        <div className="label label-success">operating normally</div>
                                    </div>
                                    <h4 className="m0">{this.camera.cameraId}</h4>
                                </div>
                                <table className="table">
                                    <tbody>
                                    <tr>
                                        <td>
                                            <strong>Location</strong>
                                        </td>
                                        <td>Unsure</td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <strong>Model</strong>
                                        </td>
                                        <td>
                                            Logitech C170
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <strong>Status</strong>
                                        </td>
                                        <td>
                                            Normal
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div className="row">
                            <Col md={9}>
                                <div className="panel b">
                                    <div className="panel-heading">
                                        <h4 className="m0">Live Feed</h4>
                                    </div>

                                    <div className="panel-body">
                                        <img className="live-image" src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + this.camera.cameraId + "/image?" + this.state.cameraImageCacheBuster} />
                                    </div>
                                </div>
                            </Col>
                            <Col md={3}>
                                <div className="panel b">
                                    <div className="panel-heading">
                                        <h4 className="m0">Calibration</h4>
                                    </div>
                                    <div className="panel-body">
                                        {this.state.cameraFrame ?
                                            this.state.cameraFrame.calibrationObject ?
                                                <div>
                                                    <p>Success! The calibration checkboard is detected.</p>
                                                    <button type="button" className="btn btn-default" onClick={this.calibrateCameraClicked.bind(this)}>Recalibrate</button>
                                                </div>
                                                :
                                                <div>
                                                    <p>The calibration checkboard is not detected. Please make sure the calibration checkboard is in view of this camera, and is aligned in the same direction as the camera.</p>
                                                </div>
                                            :
                                            <div>Loading calibration data...</div>
                                        }
                                    </div>
                                </div>
                            </Col>
                        </div>
                        <div className="panel b" id="store-layout">
                            <div className="panel-heading">
                                <h4 className="m0">Location</h4>
                            </div>

                            <div className="panel-body">
                                {this.props.showUpdateSuccess &&
                                    <Alert bsStyle="success">
                                        <p>Successfully updated the camera location.</p>
                                    </Alert>
                                }

                                {this.props.showUpdateFailure &&
                                    <Alert bsStyle="danger">
                                        <p>Failed to update the camera location.</p>
                                    </Alert>
                                }

                                <div className="store-image-container" id="store-image-container">
                                    {this.props.isUpdatingStore &&
                                        <div className="updatingOverlay">
                                            <div className="spinnerWrapper">
                                                <div className="sk-three-bounce">
                                                    <div className="sk-child sk-bounce1"></div>
                                                    <div className="sk-child sk-bounce2"></div>
                                                    <div className="sk-child sk-bounce3"></div>
                                                </div>
                                            </div>
                                        </div>
                                    }

                                    {this.state.isSelectingCalibrationObjectLocation &&
                                        <img id="calibration-object-location"
                                             src='/img/checkerboard.png'
                                             style={{
                                                 "left": this.state.calibrationObjectX - checkerboardImageOffsetX,
                                                 "top": this.state.calibrationObjectY - checkerboardImageOffsetY,
                                                 "transform": 'rotate(' + this.state.cameraRotation + "rad)"}}
                                             onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                             onClick={this.calibrationObjectLocationChosen.bind(this)}
                                        />
                                    }
                                    <img id="camera-location"
                                         src='/img/video-camera-icon.png'
                                         style={{
                                             "left": this.state.cameraX - cameraImageOffsetX,
                                             "top": this.state.cameraY - cameraImageOffsetY,
                                             "transform": 'rotate(' + this.state.cameraRotation + "rad)"}}
                                         onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                         onClick={this.cameraLocationChosen.bind(this)}
                                    />
                                    <img id="store-image"
                                         src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout"}
                                         onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                    />
                                </div>
                            </div>
                        </div>
                    </Col>
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreCameras);


