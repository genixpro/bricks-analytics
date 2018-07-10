import React from 'react';
import {Col, Row, Panel, Alert, Checkbox} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {branch} from "recompose";
import ReactTable from 'react-table'
import _ from 'underscore';
import axios from "axios/index";
import {Stomp} from 'stompjs/lib/stomp.min';
import base64 from 'base-64';
import utf8 from 'utf8';

class StoreCameras extends React.Component {
    constructor(props) {
        super(props);

        this.camera = _.findWhere(this.props.store.cameras, {cameraId: this.props.match.params.cameraId});

        this.state = {
            selectedCamera: this.props.match.params.cameraId,
            cameraImageCacheBuster: Date.now().toString(),
            cameraFrame: null,
            showCalibrationGrid: false,
            isSelectingCameraLocation: false,
            isSelectingCalibrationObjectLocation: false,
            cameraX: 0,
            cameraY: 0,
            cameraRotation: 0,
            calibrationObjectX: 0,
            calibrationObjectY: 0,
            calibrationObjectSize: 0,
            calibrationObjectRotation: 0,
            storeMapImage: null
        };

        if (this.camera) {
            var headers = {durable: false, "auto-delete": true, exclusive: true};
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
            this.state.storeMapImage = 'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout/calibrated/" + this.camera.cameraId + "?" + Date.now().toString();

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
            url: `/store/${this.props.store._id}/cameras/${this.camera.cameraId}/frame/calibration`
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
        this.setState({
            isSelectingCameraLocation: true,
            calibrationObjectSize: 100
        });
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
            this.updateCalibrationStoreMapImage();
        }
    }

    onWheelMoved(event)
    {
        if (this.state.isSelectingCalibrationObjectLocation)
        {
            const newSize = Math.max(5, this.state.calibrationObjectSize - 2 * Math.sign(event.deltaY));
            this.setState({calibrationObjectSize: newSize});
            event.preventDefault();
            this.updateCalibrationStoreMapImage();
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

    getCameraConfigurationObject()
    {
        const liveImageElem = document.getElementById('live-image');
        const storeImageElem = document.getElementById('store-image');
        const bounds = document.getElementById('store-image-container').getBoundingClientRect();

        const camera = {};
        camera.calibrationReferencePoint = {
            "x": ((this.state.calibrationObjectX - this.state.calibrationObjectSize/2) / bounds.width) * storeImageElem.naturalWidth,
            "y": ((this.state.calibrationObjectY - this.state.calibrationObjectSize/2) / bounds.height) * storeImageElem.naturalHeight,
            "unitWidth": (this.state.calibrationObjectSize / bounds.width / 7) * storeImageElem.naturalWidth,
            "unitHeight": (this.state.calibrationObjectSize / bounds.height / 5) * storeImageElem.naturalHeight
        };

        let direction = this.state.calibrationObjectRotation;

        if (this.state.cameraRotation <= (Math.PI / 4) || this.state.cameraRotation >= (Math.PI * 7.0 / 4.0))
        {
            direction += 0;
        }
        else if (this.state.cameraRotation >= (Math.PI / 4) && this.state.cameraRotation <= (Math.PI * 3.0 / 4.0))
        {
            direction += 1;
        }
        else if (this.state.cameraRotation >= (Math.PI * 3.0 / 4.0) && this.state.cameraRotation <= (Math.PI * 5.0 / 4.0))
        {
            direction += 2;
        }
        else if (this.state.cameraRotation >= (Math.PI * 5.0 / 4.0) && this.state.cameraRotation <= (Math.PI * 7.0 / 4.0))
        {
            direction += 3;
        }

        direction = direction % 4;
        if (direction === 0)
        {
            camera.calibrationReferencePoint.direction = 'north';
        }
        if (direction === 1)
        {
            camera.calibrationReferencePoint.direction = 'east';
        }
        if (direction === 2)
        {
            camera.calibrationReferencePoint.direction = 'south';
        }
        if (direction === 3)
        {
            camera.calibrationReferencePoint.direction = 'west';
        }


        camera.width = liveImageElem.naturalWidth;
        camera.height = liveImageElem.naturalHeight;

        camera.cameraLocation = {
            "x": (this.state.cameraX / bounds.width) * storeImageElem.offsetWidth,
            "y": (this.state.cameraY / bounds.height) * storeImageElem.offsetHeight,
        };

        camera.cameraMatrix = this.state.cameraFrame.calibrationObject.cameraMatrix;
        camera.rotationVector = this.state.cameraFrame.calibrationObject.rotationVector;
        camera.translationVector = this.state.cameraFrame.calibrationObject.translationVector;
        camera.distortionCoefficients = this.state.cameraFrame.calibrationObject.distortionCoefficients;
        return camera;
    }

    calibrationObjectLocationChosen(event)
    {
        if (this.state.isSelectingCalibrationObjectLocation)
        {
            if (event.button === 0)
            {
                this.setState({
                    isSelectingCameraLocation: false,
                    isSelectingCalibrationObjectLocation: false
                });
                this.updateCalibrationRotation();

                // Make the modification to the camera data.
                const newStore = this.props.store;
                const camera = _.findWhere(newStore.cameras, {cameraId: this.state.selectedCamera});
                const newCamera = this.getCameraConfigurationObject();
                Object.keys(newCamera).forEach((key) => camera[key] = newCamera[key]);

                this.props.updateStore(newStore, () => this.resetCalibrationStoreMapImage());
            }

            if (event.button == 1)
            {
                const newDirection = (this.state.calibrationObjectRotation + 1) % 4;
                this.setState({calibrationObjectRotation: newDirection});
                event.preventDefault();
                this.updateCalibrationStoreMapImage();
            }
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

    showCalibrationGridChanged()
    {
        this.setState({showCalibrationGrid: !this.state.showCalibrationGrid})
    }

    resetCalibrationStoreMapImage()
    {
        this.setState({
            storeMapImage: 'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout/calibrated/" + this.camera.cameraId + "?" + Date.now().toString()
        })
    }

    /// Throttle this so we don't update the store image too often
    updateCalibrationStoreMapImage()
    {
        if (_.isUndefined(this.updateCalibrationStoreMapImage__impl))
        {
            this.updateCalibrationStoreMapImage__impl = _.throttle(() =>
            {
                axios({
                    method: 'post',
                    url: 'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout/calibrated/" + this.camera.cameraId,
                    data: this.getCameraConfigurationObject(),
                    responseType: 'arraybuffer'
                }).then((response) =>
                {
                    const newState = {storeMapImage: 'data:image/png;base64,' + new Buffer(response.data, 'binary').toString('base64')}; // don't ask why utf8 conversion is needed here, it makes no sense to me either
                    this.setState(newState);
                });
            }, 1000);
        }
        this.updateCalibrationStoreMapImage__impl();
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
                    <Col md={2}>
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
                    <Col md={10}>
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
                            <Col md={4}>
                                <div className="panel b">
                                    <div className="panel-heading">
                                        <h4 className="m0">Live Feed</h4>
                                    </div>

                                    <div className="panel-body">
                                        {
                                            this.state.showCalibrationGrid
                                                ? <img id='live-image' className="live-image" src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + this.camera.cameraId + "/calibration?" + this.state.cameraImageCacheBuster} />
                                                : <img id='live-image' className="live-image" src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + this.camera.cameraId + "/image?" + this.state.cameraImageCacheBuster} />
                                        }
                                        <Checkbox title={"Show Calibration Grid"} checked={this.state.showCalibrationGrid} onChange={this.showCalibrationGridChanged.bind(this)}>Show Calibration Grid</Checkbox>
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
                            <Col md={8}>
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
                                                     "left": this.state.calibrationObjectX - this.state.calibrationObjectSize/2,
                                                     "top": this.state.calibrationObjectY - this.state.calibrationObjectSize/2,
                                                     "width": this.state.calibrationObjectSize
                                                 }}
                                                 onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                                 onWheel={this.onWheelMoved.bind(this)}
                                                 onClick={this.calibrationObjectLocationChosen.bind(this)}
                                            />
                                            }
                                            {   (this.state.isSelectingCameraLocation ||
                                                this.state.isSelectingCalibrationObjectLocation) &&
                                            <img id="camera-location"
                                                 src='/img/video-camera-icon.png'
                                                 style={{
                                                     "left": this.state.cameraX - cameraImageOffsetX,
                                                     "top": this.state.cameraY - cameraImageOffsetY,
                                                     "transform": 'rotate(' + this.state.cameraRotation + "rad)"
                                                 }}
                                                 onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                                 onWheel={this.onWheelMoved.bind(this)}
                                                 onClick={this.cameraLocationChosen.bind(this)}
                                            />
                                            }
                                            <img id="store-image"
                                                 className="store-image"
                                                 src={this.state.storeMapImage}
                                                 onMouseMove={this.mouseMovedOnStoreLayout.bind(this)}
                                                 onWheel={this.onWheelMoved.bind(this)}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </Col>
                        </div>
                    </Col>
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreCameras);


